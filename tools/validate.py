#!/usr/bin/env python3
"""Validate the cookbook: recipe schema, PDF structure, EPUB (epubcheck), contact sheet.

Since the content and artwork intentionally diverge from any reference, validation
is *structural*, not pixel-based:

  1. every recipes/*.md front matter conforms to schema/recipe.schema.json;
  2. build/cookbook.pdf has the right trim (6.75x9.5in) and page count;
  3. build/cookbook.epub passes epubcheck (or a structural fallback if no Java);
  4. a build/contact-sheet.png thumbnail grid is produced for eyeballing.

Exit code is non-zero if any check fails. Run: python3 tools/validate.py
"""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
RECIPES = ROOT / "recipes"

JSON_TYPE = {
    "string": str,
    "array": list,
    "object": dict,
    "boolean": bool,
    "integer": int,
    "number": (int, float),
}

failures: list[str] = []


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m" if sys.stdout.isatty() else f"\n{title}")


def ok(msg: str) -> None:
    print(f"  ok   {msg}")


def bad(msg: str) -> None:
    print(f"  FAIL {msg}")
    failures.append(msg)


# ---- 1. recipe schema ------------------------------------------------------
def validate_recipes() -> None:
    section("Recipe front matter")
    schema = json.loads((ROOT / "schema" / "recipe.schema.json").read_text())
    props = schema["properties"]
    required = schema["required"]
    allow_extra = schema.get("additionalProperties", True)

    paths = sorted(RECIPES.glob("*.md"))
    if not paths:
        bad("no recipes found")
        return
    for p in paths:
        raw = p.read_text(encoding="utf-8")
        if not raw.startswith("---"):
            bad(f"{p.name}: missing front matter")
            continue
        fm = yaml.safe_load(raw.split("---", 2)[1]) or {}
        errs = []
        for key in required:
            if not str(fm.get(key, "")).strip():
                errs.append(f"missing/empty '{key}'")
        for key, val in fm.items():
            if key not in props:
                if not allow_extra:
                    errs.append(f"unknown key '{key}'")
                continue
            spec = props[key]
            expected = spec.get("type")
            if expected and val is not None and not isinstance(val, JSON_TYPE.get(expected, object)):
                errs.append(f"'{key}' should be {expected}")
            if "enum" in spec and val not in spec["enum"]:
                errs.append(f"'{key}'='{val}' not in {spec['enum']}")
        if errs:
            bad(f"{p.name}: " + "; ".join(errs))
        else:
            ok(p.name)


# ---- 2. PDF structure ------------------------------------------------------
def validate_pdf() -> int:
    section("PDF structure")
    pdf = BUILD / "cookbook.pdf"
    if not pdf.exists():
        bad("build/cookbook.pdf not found (run `make pdf`)")
        return 0
    import fitz  # PyMuPDF

    doc = fitz.open(pdf)
    n_recipes = sum(
        1
        for p in RECIPES.glob("*.md")
        if not (yaml.safe_load(p.read_text().split("---", 2)[1]) or {}).get("draft", False)
    )
    # cover + endpaper + intro + colophon + endpaper = 5 fixed; each recipe = opener/story + method
    expected = 5 + 2 * n_recipes
    if len(doc) == expected:
        ok(f"page count = {len(doc)} (5 fixed + {n_recipes} recipes×2)")
    else:
        bad(f"page count = {len(doc)}, expected {expected}")

    w, h = doc[0].rect.width, doc[0].rect.height
    if abs(w - 486) <= 1 and abs(h - 684) <= 1:
        ok(f"trim = {w:.0f}x{h:.0f} pt (6.75x9.5 in)")
    else:
        bad(f"trim = {w:.1f}x{h:.1f} pt, expected 486x684")
    doc.close()
    return expected


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
    """Minimal EPUB sanity when epubcheck/Java is unavailable."""
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
        bad("build/cookbook.epub not found (run `make epub`)")
        return
    jar = ROOT / "tools" / "epubcheck" / "epubcheck.jar"
    java = find_java()
    if jar.exists() and java:
        res = subprocess.run([java, "-jar", str(jar), str(epub)], capture_output=True, text=True)
        tail = (res.stdout + res.stderr).strip().splitlines()[-3:]
        if res.returncode == 0:
            ok("epubcheck: " + " ".join(tail[-1:]))
        else:
            bad("epubcheck reported errors:\n      " + "\n      ".join(tail))
    else:
        print("  note: epubcheck/Java unavailable — running structural fallback")
        structural_epub_check(epub)


# ---- 4. contact sheet ------------------------------------------------------
def contact_sheet() -> None:
    section("Contact sheet")
    pdf = BUILD / "cookbook.pdf"
    if not pdf.exists():
        print("  skipped (no PDF)")
        return
    pngdir = BUILD / "pdf_png"
    pngdir.mkdir(exist_ok=True)
    for old in pngdir.glob("c-*.png"):
        old.unlink()
    subprocess.run(
        ["pdftoppm", "-r", "70", "-png", str(pdf), str(pngdir / "c")],
        check=True, capture_output=True,
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
    ok(f"wrote {out.relative_to(ROOT)} ({len(ims)} pages)")


def main() -> int:
    validate_recipes()
    validate_pdf()
    validate_epub()
    contact_sheet()
    section("Summary")
    if failures:
        print(f"  \033[31m{len(failures)} check(s) failed.\033[0m")
        return 1
    print("  All checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
