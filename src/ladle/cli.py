"""Command dispatch for the `ladle` CLI.

Each subcommand delegates to a tool module's ``main(argv)``; ``build`` chains
html -> pdf -> epub. Book-scoped commands take ``--book PATH`` (default:
``$BOOK_CONFIG`` or ``./book.yaml``).
"""
from __future__ import annotations

import sys

from . import (
    __version__,
    bake_assets,
    build_html,
    doctor,
    gen_illustrations,
    make_epub,
    make_pdf,
    new_book,
    validate,
)


def _build(argv: list[str]) -> int:
    """html -> pdf -> epub, stopping at the first failure."""
    for step in (build_html.main, make_pdf.main, make_epub.main):
        rc = step(argv)
        if rc:
            return rc
    return 0


COMMANDS = {
    "build": _build,
    "html": build_html.main,
    "pdf": make_pdf.main,
    "epub": make_epub.main,
    "illustrations": gen_illustrations.main,
    "assets": bake_assets.main,
    "validate": validate.main,
    "doctor": doctor.main,
    "new": new_book.main,
}

USAGE = f"""ladle {__version__} — build cookbooks (PDF + EPUB) from markdown.

usage: ladle <command> [options]

commands:
  build          build PDF + EPUB (html -> pdf -> epub)
  html           render print + epub HTML only
  pdf            render build/cookbook.pdf from the HTML
  epub           render build/cookbook.epub from the HTML
  illustrations  (re)generate the SVG placeholder art
  assets         re-bake the default theme's raster brand assets
  validate       schema + PDF structure + epubcheck + contact sheet
  doctor         check pandoc/poppler/WeasyPrint/Java are installed
  new            scaffold a new book under books/<name>/

Book-scoped commands accept --book PATH (default: $BOOK_CONFIG or ./book.yaml).
Run `ladle <command> --help` for a command's own options."""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "help"):
        print(USAGE)
        return 0
    if argv[0] in ("-V", "--version"):
        print(f"ladle {__version__}")
        return 0
    cmd, rest = argv[0], argv[1:]
    fn = COMMANDS.get(cmd)
    if fn is None:
        print(f"ladle: unknown command {cmd!r}\n", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2
    return fn(rest)


if __name__ == "__main__":
    raise SystemExit(main())
