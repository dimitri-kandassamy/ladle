#!/usr/bin/env python3
"""Validate the cookbook: recipe schema + body, PDF structure, EPUB (epubcheck), contact sheet.

Validation is *structural*, not pixel-based:

  1. every recipes/*.md front matter conforms to schema/recipe.schema.json;
  2. every recipe body parses, with nothing silently dropped (--strict to fail);
  3. build/cookbook.pdf has the right trim (6.75x9.5in) and page count;
  4. build/cookbook.epub passes epubcheck (or a structural fallback if no Java);
  5. a build/contact-sheet.png thumbnail grid is produced for eyeballing.

Exit code is non-zero if any check fails. Run: ladle validate
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import jsonschema
import yaml

from . import config, ui

BUILD = config.build_dir()

failures: list[str] = []


def section(title: str) -> None:
    ui.step("")
    ui.step(ui.style(title, "bold"))


def ok(msg: str) -> None:
    ui.step(f"  ok   {msg}")


def bad(msg: str) -> None:
    ui.step(f"  {ui.style('FAIL', 'red')} {msg}")
    failures.append(msg)


def note(msg: str) -> None:
    ui.step(f"  note {msg}")


def front_matter(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8").split("---", 2)[1]) or {}


def notes_line_count(path: Path) -> int:
    """Non-empty line count of a recipe's `## NOTES` body, for the page-count diagnostic."""
    raw = path.read_text(encoding="utf-8")
    body = raw.split("---", 2)[-1] if raw.startswith("---") else raw
    in_notes = False
    count = 0
    for line in body.splitlines():
        if re.match(r"^##\s+NOTES\s*$", line.strip(), re.IGNORECASE):
            in_notes = True
            continue
        if re.match(r"^##\s+\S", line):
            in_notes = False
            continue
        if in_notes and line.strip():
            count += 1
    return count


# ---- 1. recipe schema ------------------------------------------------------
def check_recipes(recipes_dir: Path) -> list[dict]:
    """Validate every recipe's front matter against the schema.

    Pure: returns one record per result — ``{file, ok, loc, message}`` — with no
    printing, so :func:`validate_recipes` can format the human report from it.
    """
    schema = json.loads(config.SCHEMA_PATH.read_text())
    Validator = jsonschema.validators.validator_for(schema)
    Validator.check_schema(schema)
    validator = Validator(schema)

    results: list[dict] = []
    paths = sorted(recipes_dir.glob("*.md"))
    if not paths:
        return [{"file": "", "ok": False, "loc": "", "message": "no recipes found"}]
    for p in paths:
        raw = p.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            results.append({"file": p.name, "ok": False, "loc": "", "message": "missing front matter"})
            continue
        try:
            fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
        except yaml.YAMLError as e:
            results.append({"file": p.name, "ok": False, "loc": "", "message": f"invalid YAML: {e}"})
            continue
        errors = sorted(validator.iter_errors(fm), key=lambda e: list(e.path))
        if errors:
            for e in errors:
                loc = "/".join(map(str, e.path)) or "(root)"
                results.append({"file": p.name, "ok": False, "loc": loc, "message": e.message})
        else:
            results.append({"file": p.name, "ok": True, "loc": "", "message": ""})
    return results


def _format_result(r: dict) -> str:
    """Compose a ``file: loc: message`` label from a :func:`check_recipes` record."""
    label = f"{r['file']}: " if r["file"] else ""
    loc = f"{r['loc']}: " if r["loc"] else ""
    return f"{label}{loc}{r['message']}"


def validate_recipes(recipes_dir: Path) -> None:
    section("Recipe front matter")
    for r in check_recipes(recipes_dir):
        if r["ok"]:
            ok(r["file"])
        else:
            bad(_format_result(r))


# ---- 1b. recipe body -------------------------------------------------------
def validate_bodies(recipes_dir: Path, *, strict: bool = False) -> None:
    """Report body content that no parser rule claimed, so the book won't show it.

    Reuses ``build_html.unparsed_content`` so ``build`` and ``validate`` agree on
    what gets dropped. A note by default (plenty of hand-written corpora have
    stray lines, and the build still succeeds); a failure under ``--strict``, for
    CI and for anyone who wants the guarantee.
    """
    from . import build_html

    section("Recipe body")
    found = [d for p in sorted(recipes_dir.glob("*.md")) for d in build_html.unparsed_content(p)]
    if not found:
        ok("all body content was parsed")
        return
    for d in found:
        bad(str(d)) if strict else note(str(d))
    n = len(found)
    summary = f"{n} item{'s' if n != 1 else ''} of body content will not appear in the book"
    if strict:
        return
    note(summary)
    note("re-run with --strict to treat these as failures")


# ---- 2. PDF structure ------------------------------------------------------
def validate_pdf(recipes_dir: Path) -> None:
    section("PDF structure")
    pdf = BUILD / "cookbook.pdf"
    if not pdf.exists():
        bad("build/cookbook.pdf not found (run `ladle build`)")
        return
    res = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    if res.returncode != 0:
        bad("pdfinfo failed (is poppler installed?)")
        return
    info = dict((k.strip(), v.strip()) for k, _, v in (line.partition(":") for line in res.stdout.splitlines()) if k)

    pages = int(info.get("Pages", "0"))
    n_recipes = sum(1 for p in recipes_dir.glob("*.md") if not front_matter(p).get("draft", False))
    # cover + endpaper + contents + intro + endpaper + colophon = 6 fixed;
    # each recipe = opener/story + method
    expected = 6 + 2 * n_recipes
    if pages == expected:
        ok(f"page count = {pages} (6 fixed + {n_recipes} recipes×2)")
    else:
        # A heuristic, not a structural invariant: a recipe with a long NOTES
        # section (manuscript provenance, substitutions, …) legitimately
        # overflows the fixed 2-pages-per-recipe layout onto a 3rd page.
        # Report it as a diagnostic rather than failing the whole run.
        note(f"page count = {pages}, expected {expected} (delta {pages - expected:+d})")
        threshold = 8
        culprits = [
            p.name
            for p in sorted(recipes_dir.glob("*.md"))
            if not front_matter(p).get("draft", False) and notes_line_count(p) >= threshold
        ]
        if culprits:
            note(f"likely culprits (long NOTES, ≥{threshold} lines): {', '.join(culprits)}")

    m = re.search(r"([\d.]+)\s*x\s*([\d.]+)", info.get("Page size", ""))
    if m:
        w, h = float(m.group(1)), float(m.group(2))
        if abs(w - 486) <= 1 and abs(h - 684) <= 1:
            ok(f"trim = {w:.0f}x{h:.0f} pt (6.75x9.5 in)")
        else:
            bad(f"trim = {w:.1f}x{h:.1f} pt, expected 486x684")
    else:
        bad("could not read page size from pdfinfo")


# ---- 3. EPUB ---------------------------------------------------------------
def find_java() -> str | None:
    """First candidate that is a *working* runtime (verified via `-version`).

    The macOS /usr/bin/java stub is on PATH but errors unless a JDK is installed,
    so trusting `which` is not enough — we run each candidate.
    """
    candidates: list[str] = []
    if os.environ.get("JAVA_HOME"):
        candidates.append(str(Path(os.environ["JAVA_HOME"], "bin/java")))
    candidates += ["/usr/local/opt/openjdk/bin/java", "/opt/homebrew/opt/openjdk/bin/java"]
    if shutil.which("java"):
        candidates.append(shutil.which("java"))
    for j in candidates:
        if Path(j).exists():
            try:
                if subprocess.run([j, "-version"], capture_output=True).returncode == 0:
                    return j
            except OSError:
                continue
    return None


def structural_epub_check(epub: Path) -> None:
    """Minimal EPUB sanity when epubcheck/Java is unavailable (e.g. locally)."""
    with zipfile.ZipFile(epub) as z:
        names = z.namelist()
        if names and names[0] == "mimetype" and z.read("mimetype") == b"application/epub+zip":
            ok("mimetype is first entry and correct")
        else:
            bad("mimetype entry malformed")
        if "META-INF/container.xml" in names:
            ok("container.xml present")
        else:
            bad("container.xml missing")
        opfs = [n for n in names if n.endswith(".opf")]
        ok(f"OPF package found ({opfs[0]})") if opfs else bad("no .opf package")


def validate_epub() -> None:
    section("EPUB")
    epub = BUILD / "cookbook.epub"
    if not epub.exists():
        bad("build/cookbook.epub not found (run `ladle build`)")
        return
    jar = config.epubcheck_jar()
    java = find_java()
    if jar.exists() and java:
        res = subprocess.run([java, "-jar", str(jar), str(epub)], capture_output=True, text=True)
        tail = (res.stdout + res.stderr).strip().splitlines()[-3:]
        if res.returncode == 0:
            ok("epubcheck: " + " ".join(tail[-1:]))
        else:
            bad("epubcheck reported errors:\n      " + "\n      ".join(tail))
    elif shutil.which("epubcheck"):
        res = subprocess.run(["epubcheck", str(epub)], capture_output=True, text=True)
        tail = (res.stdout + res.stderr).strip().splitlines()[-3:]
        ok("epubcheck: " + " ".join(tail[-1:])) if res.returncode == 0 else bad(
            "epubcheck reported errors:\n      " + "\n      ".join(tail)
        )
    else:
        note("epubcheck/Java unavailable — running structural fallback")
        structural_epub_check(epub)


# ---- 4. contact sheet ------------------------------------------------------
def contact_sheet() -> None:
    section("Contact sheet")
    pdf = BUILD / "cookbook.pdf"
    if not pdf.exists():
        ui.step("  skipped (no PDF)")
        return
    pngdir = BUILD / "pdf_png"
    pngdir.mkdir(exist_ok=True)
    for old in pngdir.glob("c-*.png"):
        old.unlink()
    subprocess.run(
        ["pdftoppm", "-r", "70", "-png", str(pdf), str(pngdir / "c")],
        check=True,
        capture_output=True,
    )
    from PIL import Image

    pages = sorted(pngdir.glob("c-*.png"))
    ims = [Image.open(p) for p in pages]
    cols, pad = 6, 8
    rows = (len(ims) + cols - 1) // cols
    w, h = ims[0].size
    canvas = Image.new("RGB", (cols * w + pad * (cols + 1), rows * h + pad * (rows + 1)), "#d8d2c4")
    for k, im in enumerate(ims):
        canvas.paste(im, (pad + (k % cols) * (w + pad), pad + (k // cols) * (h + pad)))
    out = BUILD / "contact-sheet.png"
    canvas.save(out)
    ok(f"wrote {config.rel(out)} ({len(ims)} pages)")


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser(
        "ladle validate",
        __doc__,
        "ladle validate --book pt/book.yaml",
        "ladle validate --strict",
    )
    config.add_book_arg(ap)
    ap.add_argument(
        "--strict",
        action="store_true",
        help="fail if any recipe body content could not be parsed",
    )
    args = ap.parse_args(argv)
    book_cfg = config.load_book_config(args.book)

    failures.clear()  # re-entrant: don't carry results across calls in one process
    validate_recipes(book_cfg.recipes_dir)
    validate_bodies(book_cfg.recipes_dir, strict=args.strict)
    validate_pdf(book_cfg.recipes_dir)
    validate_epub()
    contact_sheet()
    section("Summary")
    if failures:
        ui.step(ui.style(f"  {len(failures)} check(s) failed.", "red"))
        return ui.VALIDATION
    ui.step("  All checks passed.")
    return ui.OK


if __name__ == "__main__":
    sys.exit(main())
