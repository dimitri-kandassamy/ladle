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


_console = Console()


def configure(**kwargs) -> Console:
    """Install a new console from parsed global flags; returns it."""
    global _console
    _console = Console(**kwargs)
    return _console


def get() -> Console:
    return _console


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
