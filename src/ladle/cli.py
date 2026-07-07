"""Command dispatch for the `ladle` CLI.

A single command registry (:data:`COMMANDS`) is the source of truth for both
dispatch and the generated top-level help, so the two can't drift. Each command
delegates to a tool module's ``main(argv)``; ``build`` chains html -> pdf ->
epub. Book-scoped commands take ``--book PATH`` (default: ``$BOOK_CONFIG`` or
``./book.yaml``).
"""
from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

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
    """Build the book's PDF + EPUB: html -> pdf -> epub, stopping at the first failure."""
    ap = ui.command_parser(_build.__doc__, "ladle build", "ladle build --book books/pt/book.yaml")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    # Forward only what the stages understand, so a future build-only flag can't
    # break the chain by reaching a stage parser that doesn't define it.
    stage_argv = ["--book", args.book] if args.book else []
    for stage in (build_html.main, make_pdf.main, make_epub.main):
        rc = stage(stage_argv)
        if rc:
            return rc
    return ui.OK


@dataclass(frozen=True)
class Command:
    fn: Callable[[list[str]], int]
    help: str
    group: str
    book: bool = False   # meaningfully uses --book (advertised in help)


COMMANDS: dict[str, Command] = {
    "new": Command(new_book.main,
                   "scaffold a new book under books/<name>/", "Start a book"),
    "build": Command(_build,
                     "build PDF + EPUB (html -> pdf -> epub)", "Build a book", book=True),
    "html": Command(build_html.main,
                    "render print + epub HTML only", "Build a book", book=True),
    "pdf": Command(make_pdf.main,
                   "render build/cookbook.pdf from the HTML", "Build a book"),
    "epub": Command(make_epub.main,
                    "render build/cookbook.epub from the HTML", "Build a book", book=True),
    "illustrations": Command(gen_illustrations.main,
                             "(re)generate the SVG placeholder art", "Generate assets", book=True),
    "assets": Command(bake_assets.main,
                      "re-bake a theme's raster brand assets (--theme)", "Generate assets"),
    "lint": Command(lint.main,
                    "validate recipe front matter (--json/--plain)", "Inspect & validate", book=True),
    "list": Command(list_recipes.main,
                    "list recipes (--json/--plain, --category, --tag)", "Inspect & validate", book=True),
    "validate": Command(validate.main,
                        "schema + PDF structure + epubcheck + contact sheet", "Inspect & validate", book=True),
    "doctor": Command(doctor.main,
                      "check pandoc/poppler/WeasyPrint/Java installed", "Inspect & validate"),
}

_GROUP_ORDER = ["Start a book", "Build a book", "Generate assets", "Inspect & validate"]


def render_help() -> str:
    """Top-level help, generated from :data:`COMMANDS` (single source of truth).

    Headings are bold only when stdout supports it (TTY, color not disabled) —
    :func:`ui.style` no-ops otherwise, so piped/`--no-color` help stays plain.
    """
    def h(text: str) -> str:
        return ui.style(text, "bold", stream=sys.stdout)

    width = max(len(name) for name in COMMANDS)
    lines = [
        f"ladle {__version__} — build cookbooks (PDF + EPUB) from markdown.",
        "",
        f"{h('usage:')} ladle [-h] [--version] [-v | -q] [--debug] [--json | --plain]",
        "             [--no-color] [--no-input] <command> [args]",
        "",
    ]
    for group in _GROUP_ORDER:
        lines.append(h(f"{group}:"))
        lines += [f"  {name:<{width}}  {c.help}" for name, c in COMMANDS.items() if c.group == group]
        lines.append("")
    book_cmds = ", ".join(name for name, c in COMMANDS.items() if c.book)
    lines += [
        h("examples:"),
        "  ladle new --name mybook      scaffold a book",
        "  ladle build                  build the PDF + EPUB",
        "  ladle lint --json            check recipes, machine-readable",
        "",
        f"--book PATH selects the book (default: $BOOK_CONFIG or ./book.yaml) for: {book_cmds}.",
        "global flags: -v/--verbose, -q/--quiet (note: -V is --version, not verbose),",
        "              --debug, --json/--plain, --no-color, --no-input.",
        "",
        f"run `ladle <command> --help` for a command's own options.  home: {ui.REPO}",
    ]
    return "\n".join(lines)


def _dispatch(name: str, sub: list[str]) -> int:
    """Run a command, mapping its exceptions to exit codes so main() always returns."""
    command = COMMANDS.get(name)
    if command is None:
        return ui.die(f"unknown command {name!r}", ui.USAGE,
                      hint="run `ladle --help` for the command list")
    try:
        return command.fn(sub)
    except SystemExit as exc:      # a subcommand's argparse (bad flag, or --help) -> return, don't raise
        return exc.code if isinstance(exc.code, int) else ui.USAGE
    except config.NoBookError as exc:
        return ui.die(str(exc), ui.NO_BOOK, hint="run `ladle new` or pass --book PATH")
    except KeyboardInterrupt:
        return ui.INTERRUPTED
    except Exception as exc:      # noqa: BLE001 — top-level guard: clean message, or traceback under --debug
        if ui.get().debug:
            raise
        return ui.die(str(exc) or exc.__class__.__name__, ui.ERROR)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Pull the global flags out from anywhere in argv (so both `ladle --json list`
    # and `ladle list --json` work), configure the console, and dispatch the rest.
    # --help/--version are handled here, not as global flags, so `ladle <cmd>
    # --help` still reaches the subcommand's own parser.
    gargs, rest = ui.global_parser().parse_known_args(argv)
    ui.configure_from_args(gargs)

    if not rest or rest[0] in ("-h", "--help"):
        print(render_help())          # requested help -> stdout, exit 0
        return ui.OK
    if rest[0] in ("-V", "--version"):
        print(f"ladle {__version__}")
        return ui.OK
    if rest[0] == "help":             # `ladle help [command]`
        if len(rest) > 1 and rest[1] in COMMANDS:
            return _dispatch(rest[1], ["--help"])
        print(render_help())
        return ui.OK

    return _dispatch(rest[0], rest[1:])


if __name__ == "__main__":
    raise SystemExit(main())
