"""Unit tests for the shared console (ui): color gating, stream split, exit codes."""

from __future__ import annotations

import pytest

from ladle import ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()  # defaults before each test
    yield
    ui.configure()


class _Stream:
    def __init__(self, tty: bool):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


# ---- color gating ----------------------------------------------------------
def test_color_auto_follows_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    ui.configure(color=None)
    assert ui.use_color(_Stream(tty=True)) is True
    assert ui.use_color(_Stream(tty=False)) is False


def test_no_color_env_disables_even_on_tty(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    ui.configure(color=None)
    assert ui.use_color(_Stream(tty=True)) is False


def test_term_dumb_disables_even_on_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "dumb")
    ui.configure(color=None)
    assert ui.use_color(_Stream(tty=True)) is False


def test_explicit_color_flag_overrides_tty_and_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    monkeypatch.setenv("TERM", "dumb")
    ui.configure(color=True)  # forced-on beats NO_COLOR and TERM=dumb
    assert ui.use_color(_Stream(tty=False)) is True
    ui.configure(color=False)
    assert ui.use_color(_Stream(tty=True)) is False


def test_style_wraps_only_when_color_on():
    ui.configure(color=True)
    assert ui.style("x", "red") == "\033[31mx\033[0m"
    ui.configure(color=False)
    assert ui.style("x", "red") == "x"


# ---- stream routing --------------------------------------------------------
def test_step_and_error_go_to_stderr(capsys):
    ui.configure(color=False)
    ui.step("working")
    ui.error("boom")
    out = capsys.readouterr()
    assert out.out == ""
    assert "working" in out.err
    assert "error: boom" in out.err


# ---- verbosity -------------------------------------------------------------
def test_quiet_suppresses_step_but_not_errors(capsys):
    ui.configure(verbosity=-1, color=False)
    ui.step("progress")
    ui.error("still shown")
    err = capsys.readouterr().err
    assert "progress" not in err
    assert "still shown" in err


def test_detail_only_shown_when_verbose(capsys):
    ui.configure(verbosity=0)
    ui.detail("noise")
    assert capsys.readouterr().err == ""
    ui.configure(verbosity=1)
    ui.detail("noise")
    assert "noise" in capsys.readouterr().err


# ---- die -------------------------------------------------------------------
def test_die_returns_code_and_prints_hint(capsys):
    ui.configure(color=False)
    code = ui.die("no book", ui.NO_BOOK, hint="run `ladle new`")
    assert code == ui.NO_BOOK == 3
    err = capsys.readouterr().err
    assert "error: no book" in err
    assert "hint: run `ladle new`" in err


# ---- confirm / interactive -------------------------------------------------
def test_confirm_assume_yes_never_prompts(monkeypatch):
    # Even on a TTY, --yes answers True without calling input().
    monkeypatch.setattr(ui.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("should not prompt"))
    assert ui.confirm("go?", assume_yes=True) is True


def test_confirm_non_interactive_returns_default_without_prompting(monkeypatch):
    # No TTY -> never blocks; returns the given default.
    monkeypatch.setattr(ui.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("should not prompt"))
    assert ui.confirm("go?", default=False) is False
    assert ui.confirm("go?", default=True) is True


def test_confirm_no_input_flag_returns_default(monkeypatch):
    monkeypatch.setattr(ui.sys.stdin, "isatty", lambda: True)  # TTY, but --no-input set
    ui.configure(no_input=True)
    monkeypatch.setattr("builtins.input", lambda *_: pytest.fail("should not prompt"))
    assert ui.confirm("go?", default=False) is False


@pytest.mark.parametrize(
    "typed,default,expected",
    [("y", False, True), ("yes", False, True), ("n", True, False), ("", True, True), ("", False, False)],
)
def test_confirm_parses_tty_answer(monkeypatch, typed, default, expected):
    monkeypatch.setattr(ui.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: typed)
    assert ui.confirm("go?", default=default) is expected


# ---- check reports ---------------------------------------------------------
def test_check_labels_align_messages_at_one_column(capsys):
    """The reason this formatting is centralised: three commands share the column."""
    ui.configure(color=False)
    ui.check_ok("passed")
    ui.check_note("informational")
    ui.check_note("optional dep missing", "warn")
    ui.check_fail("broke")

    lines = capsys.readouterr().err.splitlines()
    assert lines == [
        "  ok   passed",
        "  note informational",
        "  warn optional dep missing",
        "  FAIL broke",
    ]


def test_section_prints_a_blank_line_then_a_heading(capsys):
    ui.configure(color=False)
    ui.section("PDF structure")
    assert capsys.readouterr().err == "\nPDF structure\n"


def test_check_reports_go_to_stderr_not_stdout(capsys):
    ui.configure(color=False)
    ui.check_ok("passed")
    ui.check_fail("broke")
    out = capsys.readouterr()
    assert out.out == ""  # stdout stays clean for piping
