#!/usr/bin/env python3
"""Render build/cookbook.html -> build/cookbook.pdf with WeasyPrint.

WeasyPrint paginates and prints the art-directed print HTML directly in Python —
no browser. The print CSS uses CSS Paged Media (`@page`, fixed-size pages, page
breaks) plus transforms and pre-rendered raster backgrounds, all of which
WeasyPrint supports natively.

The PDF stage of `ladle build` (not a standalone command).
"""

from __future__ import annotations

from weasyprint import HTML

from . import config, ui


def open_outline(document, pdf) -> None:
    """Ask viewers to show the bookmark outline (table of contents) on open.

    WeasyPrint builds the outline from the HTML headings; this only flips the
    document's PageMode so the panel isn't collapsed by default.
    """
    pdf.catalog["PageMode"] = "/UseOutlines"


def render() -> int:
    """Render build/cookbook.html -> build/cookbook.pdf."""
    build = config.build_dir()
    inp = build / "cookbook.html"
    out = build / "cookbook.pdf"
    if not inp.exists():
        return ui.die(f"missing {config.rel(inp)}", ui.ERROR, hint="run `ladle build`")
    HTML(filename=str(inp)).write_pdf(str(out), finisher=open_outline)
    ui.success(f"Wrote {config.rel(out)}")
    return 0
