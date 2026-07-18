"""Command dispatch for the `ladle` CLI.

A single command registry (:data:`COMMANDS`) is the source of truth for both
dispatch and the generated top-level help, so the two can't drift. Each command
delegates to a tool module's ``main(argv)``; ``build`` chains html -> pdf ->
epub. Book-scoped commands take ``--book PATH`` (default: ``./book.yaml``).
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from dataclasses import dataclass

from . import (
    __version__,
    build_html,
    config,
    doctor,
    make_epub,
    make_pdf,
    new_book,
    theme,
    ui,
    validate,
)


def _build(argv: list[str]) -> int:
    """Build the book's PDF + EPUB: html -> pdf -> epub, stopping at the first failure."""
    ap = ui.command_parser("ladle build", _build.__doc__, "ladle build --book pt/book.yaml")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    # The stages are internal functions, not commands: html -> pdf -> epub.
    ui.detail("stage: html")
    rc = build_html.render(args.book)
    if rc:
        return rc
    ui.detail("stage: pdf")
    rc = make_pdf.render()
    if rc:
        return rc
    ui.detail("stage: epub")
    return make_epub.render(args.book)


@dataclass(frozen=True)
class Command:
    fn: Callable[[list[str]], int]
    help: str
    book: bool = False  # meaningfully uses --book (advertised in help)


COMMANDS: dict[str, Command] = {
    "new": Command(new_book.main, "scaffold a new book in ./<name>/"),
    "build": Command(_build, "build PDF + EPUB (html -> pdf -> epub)", book=True),
    "validate": Command(validate.main, "schema + PDF structure + epubcheck + contact sheet", book=True),
    "theme": Command(theme.main, "work with themes (theme lint / theme preview)"),
    "doctor": Command(doctor.main, "check pandoc/poppler/WeasyPrint/Java installed"),
}


def render_help() -> str:
    """Top-level help, generated from :data:`COMMANDS` + the global flags (single
    source of truth). Headings are bold only when stdout supports it (TTY, color
    not disabled) — :func:`ui.style` no-ops otherwise, so piped help stays plain.
    """

    def h(text: str) -> str:
        return ui.style(text, "bold", stream=sys.stdout)

    cw = max(len(name) for name in COMMANDS)
    # --help/--version are top-level actions (shown in USAGE), not global flags:
    # unlike the flags below, they don't apply after a command.
    flag_rows = ui.global_flags_help()
    fw = max(len(flags) for flags, _ in flag_rows)
    book_cmds = ", ".join(name for name, c in COMMANDS.items() if c.book)

    lines = [
        "build cookbooks (PDF + EPUB) from markdown.",
        "",
        h("USAGE"),
        "  ladle [-v | -q] [--color] [--no-input] <command> [args]",
        "  ladle (-V | --version)      print the version and exit",
        "  ladle (-h | --help)         show this help and exit",
        "",
        h("COMMANDS"),
        *(f"  {name:<{cw}}  {c.help}" for name, c in COMMANDS.items()),
        "",
        h("GLOBAL FLAGS"),
        *(f"  {flags:<{fw}}  {desc}" for flags, desc in flag_rows),
        "",
        h("EXAMPLES"),
        "  ladle new mybook             scaffold ./mybook/",
        "  ladle build                  build the PDF + EPUB",
        "  ladle validate               check recipes, PDF, EPUB",
        "",
        f"--book PATH selects the book (default: ./book.yaml) for: {book_cmds}.",
        f"run `ladle <command> --help` for a command's options.  home: {ui.REPO}",
    ]
    return "\n".join(lines)


def _dispatch(name: str, sub: list[str]) -> int:
    """Run a command, mapping its exceptions to exit codes so main() always returns."""
    command = COMMANDS.get(name)
    if command is None:
        return ui.die(f"unknown command {name!r}", ui.USAGE, hint="run `ladle --help` for the command list")
    try:
        return command.fn(sub)
    except SystemExit as exc:  # a subcommand's argparse (bad flag, or --help) -> return, don't raise
        return exc.code if isinstance(exc.code, int) else ui.USAGE
    except config.NoBookError as exc:
        return ui.die(str(exc), ui.NO_BOOK, hint="run `ladle new` or pass --book PATH")
    except config.ConfigError as exc:
        return ui.die(str(exc), ui.ERROR, hint="check the file's syntax and required fields")
    except KeyboardInterrupt:
        return ui.INTERRUPTED
    except Exception as exc:  # noqa: BLE001 — top-level guard: clean message, or traceback under -v
        if ui.get().verbosity >= 1:
            raise
        return ui.die(str(exc) or exc.__class__.__name__, ui.ERROR)


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)

    # Pull the global flags out from anywhere in argv (so both `ladle -v build`
    # and `ladle build -v` work), configure the console, and dispatch the rest.
    # --help/--version are top-level actions handled here (not stripped as globals),
    # so they act before a command: `ladle <cmd> --help` reaches the subcommand's
    # own parser, and `--version` is top-level only (matching git/cargo/pip).
    gargs, rest = ui.global_parser().parse_known_args(argv)
    ui.configure_from_args(gargs)

    if not rest or rest[0] in ("-h", "--help"):
        print(render_help())  # requested help -> stdout, exit 0
        return ui.OK
    if rest[0] in ("-V", "--version"):
        print(f"ladle {__version__}")
        return ui.OK
    if rest[0] == "help":  # `ladle help [command]`
        if len(rest) > 1 and rest[1] in COMMANDS:
            return _dispatch(rest[1], ["--help"])
        print(render_help())
        return ui.OK

    return _dispatch(rest[0], rest[1:])


if __name__ == "__main__":
    raise SystemExit(main())
