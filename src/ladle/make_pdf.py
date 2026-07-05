#!/usr/bin/env python3
"""Render build/cookbook.html -> build/cookbook.pdf with WeasyPrint.

WeasyPrint paginates and prints the art-directed print HTML directly in Python —
no browser. The print CSS uses CSS Paged Media (`@page`, fixed-size pages, page
breaks) plus transforms and pre-rendered raster backgrounds, all of which
WeasyPrint supports natively.

Run: ladle pdf
"""
from __future__ import annotations

import sys
from pathlib import Path

from weasyprint import HTML

from . import config


def open_outline(document, pdf) -> None:
    """Ask viewers to show the bookmark outline (table of contents) on open.

    WeasyPrint builds the outline from the HTML headings; this only flips the
    document's PageMode so the panel isn't collapsed by default.
    """
    pdf.catalog["PageMode"] = "/UseOutlines"


def main(argv: list[str] | None = None) -> int:
    build = config.build_dir()
    inp = build / "cookbook.html"
    out = build / "cookbook.pdf"
    if not inp.exists():
        print(f"Missing {config.rel(inp)} — run `ladle html` first.", file=sys.stderr)
        return 1
    HTML(filename=str(inp)).write_pdf(str(out), finisher=open_outline)
    print(f"Wrote {config.rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
