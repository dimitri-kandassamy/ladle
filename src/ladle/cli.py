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
    config,
    doctor,
    gen_illustrations,
    lint,
    list_recipes,
    make_epub,
    make_pdf,
    new_book,
    ui,
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
    "lint": lint.main,
    "list": list_recipes.main,
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
  lint           validate recipe front matter (--json/--plain)
  list           list a book's recipes (--json/--plain, --category, --tag)
  validate       schema + PDF structure + epubcheck + contact sheet
  doctor         check pandoc/poppler/WeasyPrint/Java are installed
  new            scaffold a new book under books/<name>/

Book-scoped commands accept --book PATH (default: $BOOK_CONFIG or ./book.yaml).
Global flags: -v/-q, --debug, --json/--plain, --no-color, --no-input.
Run `ladle <command> --help` for a command's own options."""


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Pull the global flags out from anywhere in argv (so both `ladle --json list`
    # and `ladle list --json` work), configure the console, and dispatch on what
    # remains. Global flags are store_true/count, so parse_known_args never
    # swallows a command or its own flags (e.g. --book stays in `rest`).
    gargs, rest = ui.global_parser().parse_known_args(argv)
    ui.configure_from_args(gargs)

    if not rest or rest[0] in ("-h", "--help", "help"):
        print(USAGE)              # help is requested output -> stdout, exit 0
        return ui.OK
    if rest[0] in ("-V", "--version"):
        print(f"ladle {__version__}")
        return ui.OK

    cmd, sub = rest[0], rest[1:]
    fn = COMMANDS.get(cmd)
    if fn is None:
        return ui.die(f"unknown command {cmd!r}", ui.USAGE,
                      hint="run `ladle --help` for the command list")

    try:
        return fn(sub)
    except config.NoBookError as exc:
        return ui.die(str(exc), ui.NO_BOOK, hint="run `ladle new` or pass --book PATH")
    except KeyboardInterrupt:
        return ui.die("interrupted", ui.ERROR)
    except Exception as exc:      # noqa: BLE001 — top-level guard: clean message, or traceback under --debug
        if ui.get().debug:
            raise
        return ui.die(str(exc) or exc.__class__.__name__, ui.ERROR)


if __name__ == "__main__":
    raise SystemExit(main())
