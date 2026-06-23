#!/usr/bin/env python3
"""Render build/cookbook.html -> build/cookbook.pdf with WeasyPrint.

WeasyPrint paginates and prints the art-directed print HTML directly in Python —
no browser. The print CSS uses CSS Paged Media (`@page`, fixed-size pages, page
breaks) plus transforms and pre-rendered raster backgrounds, all of which
WeasyPrint supports natively.

Run: python3 tools/make_pdf.py
"""
from __future__ import annotations

import sys
from pathlib import Path

from weasyprint import HTML

ROOT = Path(__file__).resolve().parent.parent
INPUT = ROOT / "build" / "cookbook.html"
OUTPUT = ROOT / "build" / "cookbook.pdf"


def main() -> int:
    if not INPUT.exists():
        print("Missing build/cookbook.html — run `python3 tools/build_html.py` first.", file=sys.stderr)
        return 1
    HTML(filename=str(INPUT)).write_pdf(str(OUTPUT))
    print(f"Wrote {OUTPUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
