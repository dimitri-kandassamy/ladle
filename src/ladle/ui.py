"""Shared console: stdout(data)/stderr(logs) split, color gating, exit codes.

Configured once from the global CLI flags (see ``cli.py``); every command routes
output through here so streams, color, and verbosity stay consistent.

The contract (clig.dev):

* **stderr carries everything a command says** — progress, status, warnings,
  errors. Use :func:`step` / :func:`success` / :func:`warn` / :func:`error` /
  :func:`die`.
* **stdout is reserved for machine output** — no command emits any today, so it
  stays clean for piping (a future ``ingest``/``theme list`` would use it).

Color is emitted only when the target stream is a TTY, ``NO_COLOR`` is unset, and
``TERM`` isn't ``dumb`` — unless a ``--color``/``--no-color`` flag forces it (see
:class:`Console`).
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
INTERRUPTED = 130  # 128 + SIGINT, the conventional code for a Ctrl-C exit

_ANSI = {"bold": "1", "dim": "2", "red": "31", "green": "32", "yellow": "33"}

REPO = "https://github.com/dimitri-kandassamy/ladle"


@dataclass
class Console:
    """Runtime output settings, configured once from the global flags."""

    verbosity: int = 0  # -q -> -1 (errors only), default 0, -v -> +1
    color: bool | None = None  # None = auto (TTY + NO_COLOR); True/False = forced
    no_input: bool = False


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
    g.add_argument("-v", "--verbose", action="count", default=0, help="more detail on stderr; full traceback on error")
    g.add_argument("-q", "--quiet", action="store_true", help="only errors on stderr")
    g.add_argument(
        "--color",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="force color on/off (default: auto — honors TTY and NO_COLOR)",
    )
    g.add_argument("--no-input", dest="no_input", action="store_true", help="never prompt; use defaults or fail")
    return parser


def global_flags_help() -> list[tuple[str, str]]:
    """``(flag names, help)`` rows for each global flag, read off the parser.

    Derived from :func:`add_global_flags` so the help listing can't drift from
    the flags actually accepted.
    """
    return [(", ".join(a.option_strings), a.help or "") for a in global_parser()._actions if a.option_strings]


def global_parser() -> argparse.ArgumentParser:
    """A standalone parser holding only the global flags (for pre-parsing).

    ``allow_abbrev=False`` so pre-stripping a global never greedily matches an
    abbreviated subcommand flag. Constraint: no subcommand flag may share a name
    with a global (it would be consumed here before the subcommand sees it).
    """
    return add_global_flags(argparse.ArgumentParser(add_help=False, allow_abbrev=False))


def command_parser(prog: str, description: str | None, *examples: str) -> argparse.ArgumentParser:
    """An ``ArgumentParser`` with a consistent examples + repo-link epilog.

    Every subcommand uses this so ``ladle <cmd> --help`` leads with usage and
    ends with runnable examples and the project home. *prog* (e.g. ``"ladle
    validate"``) fixes the usage line, which argparse otherwise derives from
    ``sys.argv[0]`` (``__main__.py`` when run via ``python -m ladle``).
    """
    # Bold the labels only when stdout supports it (argparse prints help there).
    footer = [f"{style('home:', 'bold', stream=sys.stdout)} {REPO}"]
    if examples:
        footer = [style("examples:", "bold", stream=sys.stdout), *(f"  {e}" for e in examples), "", *footer]
    return argparse.ArgumentParser(
        prog=prog,
        description=description,
        epilog="\n".join(footer),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )


def configure_from_args(args: argparse.Namespace) -> Console:
    """Build the console from parsed global flags (quiet wins over verbose)."""
    verbosity = -1 if getattr(args, "quiet", False) else getattr(args, "verbose", 0)
    color = getattr(args, "color", None)  # True (--color) / False (--no-color) / None (auto)
    return configure(
        verbosity=verbosity,
        color=color,
        no_input=getattr(args, "no_input", False),
    )


# ---- color ----------------------------------------------------------------
def use_color(stream=sys.stderr) -> bool:
    """Whether to emit ANSI on *stream* given the flags/env/TTY state.

    Precedence (matches supports-color/Rich/termcolor): a forced ``--color`` /
    ``--no-color`` wins; then ``NO_COLOR``; then ``TERM=dumb`` (a terminfo entry
    with no color capability — e.g. Emacs' ``M-x shell`` runs on a real TTY but
    exports it); finally the TTY test.
    """
    if _console.color is not None:
        return _console.color
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("TERM") == "dumb":
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def style(text: str, *styles: str, stream=sys.stderr) -> str:
    """Wrap *text* in ANSI *styles*, or return it unchanged when color is off."""
    if not styles or not use_color(stream):
        return text
    codes = ";".join(_ANSI[s] for s in styles)
    return f"\033[{codes}m{text}\033[0m"


# ---- routing --------------------------------------------------------------
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


# ---- interaction ----------------------------------------------------------
def interactive() -> bool:
    """Whether we may prompt: a real stdin TTY and ``--no-input`` not set."""
    return sys.stdin.isatty() and not _console.no_input


def confirm(question: str, *, default: bool = False, assume_yes: bool = False) -> bool:
    """Ask a yes/no *question* on stderr; return the answer. Never hangs.

    ``assume_yes`` (e.g. from a ``--yes`` flag) answers True without asking.
    When we can't prompt (no TTY or ``--no-input``) the *default* is returned
    silently, so scripts and pipes never block.
    """
    if assume_yes:
        return True
    if not interactive():
        return default
    suffix = " [Y/n] " if default else " [y/N] "
    try:
        answer = input(style(question, "bold") + suffix).strip().lower()
    except EOFError:
        return default
    if not answer:
        return default
    return answer in ("y", "yes")
