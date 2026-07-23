#!/usr/bin/env python3
"""Validate the cookbook: recipe schema + body, PDF structure, EPUB (epubcheck), contact sheet.

Validation is *structural*, not pixel-based:

  1. every recipes/*.md front matter conforms to schema/recipe.schema.json;
  2. every recipe body parses, with nothing silently dropped (--strict to fail);
  3. build/cookbook.pdf has the right trim (6.75x9.5in) and page count;
  4. build/cookbook.epub passes epubcheck (or a structural fallback if no Java);
  5. build/contact-sheet.png thumbnail grid(s) are produced for eyeballing (a
     long book paginates into contact-sheet-02.png … so no single image exceeds
     the ~16384px canvas limit that leaves it unopenable).

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


section = ui.section
ok = ui.check_ok
note = ui.check_note


def bad(msg: str) -> None:
    """Report a failing check and record it for the summary/exit code."""
    ui.check_fail(msg)
    failures.append(msg)


def _split_or_empty(path: Path) -> tuple[dict, str]:
    """Front matter + body, or ``({}, "")`` when the file cannot be split.

    Two jobs in one place. It delegates to :func:`build_html.split_front_matter`
    so ``validate`` and ``build`` agree on what front matter *is* — this file
    used to split on ``---`` by hand in three different ways, one of which raised
    a bare ``IndexError`` on a recipe with no front matter.

    And it sets the policy for the structural checks downstream: ``validate``
    *reports* a malformed recipe (:func:`check_recipes` names it, strictly) and
    keeps going, rather than aborting the run on the one file the author most
    needs a report about.
    """
    from . import build_html

    try:
        return build_html.split_front_matter(path.read_text(encoding="utf-8"), where=path.name)
    except (config.ConfigError, yaml.YAMLError):
        return {}, ""


def front_matter(path: Path) -> dict:
    return _split_or_empty(path)[0]


def notes_line_count(path: Path) -> int:
    """Non-empty line count of a recipe's `## NOTES` body, for the page-count diagnostic."""
    body = _split_or_empty(path)[1]
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
    from . import build_html

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
            fm = build_html.split_front_matter(raw, where=p.name)[0]
        except yaml.YAMLError as e:
            results.append({"file": p.name, "ok": False, "loc": "", "message": f"invalid YAML: {e}"})
            continue
        except config.ConfigError as e:
            # Unclosed `---`: reported per file so one bad recipe doesn't abort the run.
            results.append({"file": p.name, "ok": False, "loc": "", "message": str(e).split(": ", 1)[-1]})
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
    found = []
    for p in sorted(recipes_dir.glob("*.md")):
        try:
            found.extend(build_html.unparsed_content(p))
        except config.ConfigError:
            continue  # unsplittable front matter — already named in the section above
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
def _pdfinfo(pdf: Path) -> dict[str, str]:
    """`pdfinfo`'s ``Key: value`` fields, or ``{}`` if poppler is missing or fails.

    Catching OSError matters: an absent `pdfinfo` raises FileNotFoundError rather
    than returning non-zero, so the "is poppler installed?" message this feeds
    used to be unreachable — the run died on the raw errno instead.
    """
    try:
        res = subprocess.run(["pdfinfo", str(pdf)], capture_output=True, text=True)
    except OSError:
        return {}
    if res.returncode != 0:
        return {}
    fields = (line.partition(":") for line in res.stdout.splitlines())
    return {k.strip(): v.strip() for k, _, v in fields if k.strip()}


def validate_pdf(recipes_dir: Path) -> None:
    section("PDF structure")
    pdf = BUILD / "cookbook.pdf"
    if not pdf.exists():
        bad("build/cookbook.pdf not found (run `ladle build`)")
        return
    info = _pdfinfo(pdf)
    if not info:
        bad("pdfinfo failed (is poppler installed?)")
        return

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
        if opfs:
            ok(f"OPF package found ({opfs[0]})")
        else:
            bad("no .opf package")


def _run_epubcheck(command: list[str], epub: Path) -> None:
    """Run one epubcheck invocation and report its last few lines of output.

    The bundled jar and a PATH-installed `epubcheck` differ only in how they are
    launched, so the reporting lives here once.
    """
    res = subprocess.run([*command, str(epub)], capture_output=True, text=True)
    tail = (res.stdout + res.stderr).strip().splitlines()[-3:]
    if res.returncode == 0:
        ok("epubcheck: " + " ".join(tail[-1:]))
    else:
        bad("epubcheck reported errors:\n      " + "\n      ".join(tail))


def validate_epub() -> None:
    section("EPUB")
    epub = BUILD / "cookbook.epub"
    if not epub.exists():
        bad("build/cookbook.epub not found (run `ladle build`)")
        return
    jar = config.epubcheck_jar()
    java = find_java()
    if jar.exists() and java:
        _run_epubcheck([java, "-jar", str(jar)], epub)
    elif shutil.which("epubcheck"):
        _run_epubcheck(["epubcheck"], epub)
    else:
        note("epubcheck/Java unavailable — running structural fallback")
        structural_epub_check(epub)


# ---- 4. contact sheet ------------------------------------------------------
# Rasterize small (160px-wide thumbnails, not reading-resolution) and in parallel
# page-range slices — a 224pp book went 147s -> ~9s in measurement. Compose into
# one or more fixed-height sheets so a long book never yields a single strip taller
# than the ~16384px canvas dimension most viewers can open.
CONTACT_COLS = 6
CONTACT_PAD = 8
CONTACT_ROWS_PER_SHEET = 15  # 15×6 = 90 thumbnails/sheet, ~3500px tall — safely openable
CONTACT_WORKERS = 4
CONTACT_SCALE_X = 160
CONTACT_BG = "#d8d2c4"


def _pdf_page_count(pdf: Path) -> int:
    """Page count via pdfinfo; 0 if unavailable (caller renders as a single slice)."""
    return int(_pdfinfo(pdf).get("Pages", "").strip() or 0)


def _page_ranges(n_pages: int, workers: int) -> list[tuple[int, int]]:
    """Split 1..n_pages into up to *workers* contiguous (first, last) slices.

    Empty when the count is unknown (<=0), signalling a single whole-document render.
    """
    if n_pages <= 0:
        return []
    workers = max(1, min(workers, n_pages))
    per = -(-n_pages // workers)  # ceil
    ranges = []
    start = 1
    while start <= n_pages:
        last = min(start + per - 1, n_pages)
        ranges.append((start, last))
        start = last + 1
    return ranges


def _rasterize_parallel(pdf: Path, pngdir: Path, n_pages: int) -> list[Path]:
    """Render every page to pngdir/c-*.png via concurrent page-range workers.

    poppler zero-pads the page-number suffix against the whole document (not the
    slice), so every worker agrees on width and sorted(glob) is global page order.
    """
    base = ["pdftoppm", "-scale-to-x", str(CONTACT_SCALE_X), "-scale-to-y", "-1", "-png"]
    ranges = _page_ranges(n_pages, CONTACT_WORKERS)
    cmds = (
        [base + ["-f", str(first), "-l", str(last), str(pdf), str(pngdir / "c")] for first, last in ranges]
        if ranges
        else [base + [str(pdf), str(pngdir / "c")]]
    )
    procs = [subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE) for cmd in cmds]
    for proc in procs:
        _, err = proc.communicate()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, proc.args, stderr=err)
    return sorted(pngdir.glob("c-*.png"))


def _compose_sheets(images: list) -> list:
    """Paste uniform page thumbnails into fixed-height contact sheets (grid, paginated)."""
    from PIL import Image

    cols, pad, per_sheet = CONTACT_COLS, CONTACT_PAD, CONTACT_COLS * CONTACT_ROWS_PER_SHEET
    sheets = []
    for base in range(0, len(images), per_sheet):
        chunk = images[base : base + per_sheet]
        w, h = chunk[0].size
        rows = (len(chunk) + cols - 1) // cols
        canvas = Image.new("RGB", (cols * w + pad * (cols + 1), rows * h + pad * (rows + 1)), CONTACT_BG)
        for k, im in enumerate(chunk):
            canvas.paste(im, (pad + (k % cols) * (w + pad), pad + (k // cols) * (h + pad)))
        sheets.append(canvas)
    return sheets


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

    try:
        pages = _rasterize_parallel(pdf, pngdir, _pdf_page_count(pdf))
    except (OSError, subprocess.CalledProcessError):
        bad("pdftoppm failed (is poppler installed?)")
        return
    if not pages:
        bad("pdftoppm produced no page images")
        return

    from PIL import Image

    sheets = _compose_sheets([Image.open(p) for p in pages])
    # Sheet 1 keeps the canonical name (landing page, docs, CI all point at it);
    # overflow sheets are numbered from 02 so a long book stays openable.
    for old in BUILD.glob("contact-sheet-*.png"):
        old.unlink()
    outs = [BUILD / "contact-sheet.png", *(BUILD / f"contact-sheet-{i:02d}.png" for i in range(2, len(sheets) + 1))]
    for sheet, out in zip(sheets, outs, strict=True):
        sheet.save(out)
    if len(sheets) == 1:
        ok(f"wrote {config.rel(outs[0])} ({len(pages)} pages)")
    else:
        ok(f"wrote {len(sheets)} sheets ({config.rel(outs[0])} + …-{len(sheets):02d}.png, {len(pages)} pages)")


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
