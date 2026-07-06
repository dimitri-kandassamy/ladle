"""Unit tests for the shared console (ui): color gating, stream split, exit codes."""
from __future__ import annotations

import pytest

from ladle import ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()          # defaults before each test
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
    ui.configure(color=None)
    assert ui.use_color(_Stream(tty=True)) is True
    assert ui.use_color(_Stream(tty=False)) is False


def test_no_color_env_disables_even_on_tty(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    ui.configure(color=None)
    assert ui.use_color(_Stream(tty=True)) is False


def test_explicit_color_flag_overrides_tty_and_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    ui.configure(color=True)
    assert ui.use_color(_Stream(tty=False)) is True
    ui.configure(color=False)
    assert ui.use_color(_Stream(tty=True)) is False


def test_style_wraps_only_when_color_on():
    ui.configure(color=True)
    assert ui.style("x", "red") == "\033[31mx\033[0m"
    ui.configure(color=False)
    assert ui.style("x", "red") == "x"


# ---- stream routing --------------------------------------------------------
def test_data_goes_to_stdout(capsys):
    ui.data("payload")
    out = capsys.readouterr()
    assert out.out == "payload\n"
    assert out.err == ""


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
