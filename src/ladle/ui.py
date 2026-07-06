"""Shared console: stdout(data)/stderr(logs) split, color gating, exit codes.

Configured once from the global CLI flags (see ``cli.py``); every command routes
output through here so streams, color, and verbosity stay consistent.

The contract (clig.dev):

* **stdout is the machine channel** — only a command's primary *data* (a data
  command's table, or its ``--json``/``--plain`` output). Use :func:`data`.
* **stderr carries everything else** — progress, status, warnings, errors. Use
  :func:`step` / :func:`success` / :func:`warn` / :func:`error` / :func:`die`.

Color is emitted only when the target stream is a TTY and ``NO_COLOR`` is unset,
unless a ``--color``/``--no-color`` flag forces it (see :class:`Console`).
"""
from __future__ import annotations

import argparse
import os
import sys
from dataclasses import dataclass

# Exit codes. Kept small and stable — scripts key off these.
# 5 (source/extraction) is reserved for the future `ingest` command.
OK = 0
ERROR = 1
USAGE = 2
NO_BOOK = 3
VALIDATION = 4

_ANSI = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33"}


@dataclass
class Console:
    """Runtime output settings, configured once from the global flags."""

    verbosity: int = 0          # -q -> -1 (errors only), default 0, -v -> +1
    json: bool = False
    plain: bool = False
    color: bool | None = None   # None = auto (TTY + NO_COLOR); True/False = forced
    no_input: bool = False
    debug: bool = False         # show full tracebacks instead of a one-line error


_console = Console()


def configure(**kwargs) -> Console:
    """Install a new console (defaults for anything unset); returns it."""
    global _console
    _console = Console(**kwargs)
    return _console


def get() -> Console:
    return _console


# ---- global flags ---------------------------------------------------------
def add_global_flags(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    """Attach the clig.dev pragmatic-core global flags to *parser*."""
    g = parser.add_argument_group("global options")
    g.add_argument("-v", "--verbose", action="count", default=0, help="more detail on stderr")
    g.add_argument("-q", "--quiet", action="store_true", help="only errors on stderr")
    g.add_argument("--debug", action="store_true", help="developer output + full tracebacks")
    g.add_argument("--json", action="store_true", help="machine-readable JSON (data commands)")
    g.add_argument("--plain", action="store_true", help="tab-separated output (data commands)")
    g.add_argument("--no-color", dest="no_color", action="store_true",
                   help="disable color (also honors NO_COLOR / non-TTY)")
    g.add_argument("--no-input", dest="no_input", action="store_true",
                   help="never prompt; use defaults or fail")
    return parser


def global_parser() -> argparse.ArgumentParser:
    """A standalone parser holding only the global flags (for pre-parsing)."""
    return add_global_flags(argparse.ArgumentParser(add_help=False))


def configure_from_args(args: argparse.Namespace) -> Console:
    """Build the console from parsed global flags (quiet wins over verbose)."""
    verbosity = -1 if getattr(args, "quiet", False) else getattr(args, "verbose", 0)
    color = False if getattr(args, "no_color", False) else None
    return configure(
        verbosity=verbosity,
        json=getattr(args, "json", False),
        plain=getattr(args, "plain", False),
        color=color,
        no_input=getattr(args, "no_input", False),
        debug=getattr(args, "debug", False),
    )


# ---- color ----------------------------------------------------------------
def use_color(stream=sys.stderr) -> bool:
    """Whether to emit ANSI on *stream* given the flags/env/TTY state."""
    if _console.color is not None:
        return _console.color
    if os.environ.get("NO_COLOR") is not None:
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def style(text: str, *styles: str, stream=sys.stderr) -> str:
    """Wrap *text* in ANSI *styles*, or return it unchanged when color is off."""
    if not styles or not use_color(stream):
        return text
    codes = ";".join(_ANSI[s] for s in styles)
    return f"\033[{codes}m{text}\033[0m"


# ---- routing --------------------------------------------------------------
def data(text: str = "") -> None:
    """Primary machine output → **stdout** (the scripting channel)."""
    print(text)


def step(msg: str = "") -> None:
    """Progress/status → stderr. Suppressed under ``-q`` (verbosity < 0)."""
    if _console.verbosity >= 0:
        print(msg, file=sys.stderr)


def detail(msg: str) -> None:
    """Extra diagnostics → stderr, shown only under ``-v`` (verbosity >= 1)."""
    if _console.verbosity >= 1:
        print(msg, file=sys.stderr)


def success(msg: str) -> None:
    """Success line → stderr (e.g. ``Wrote build/cookbook.pdf``)."""
    if _console.verbosity >= 0:
        print(style(msg, "green"), file=sys.stderr)


def warn(msg: str) -> None:
    """Warning → stderr. Always shown (``-q`` mutes progress, not problems)."""
    print(style(f"warning: {msg}", "yellow"), file=sys.stderr)


def error(msg: str) -> None:
    """Error → stderr. Always shown."""
    print(style(f"error: {msg}", "red"), file=sys.stderr)


def die(msg: str, code: int = ERROR, hint: str | None = None) -> int:
    """Print an error (+ optional next-step hint) to stderr; return *code*.

    Callers ``return ui.die(...)`` so the exit code flows out through ``main``.
    """
    error(msg)
    if hint:
        print(f"  hint: {hint}", file=sys.stderr)
    return code
