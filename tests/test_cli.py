"""Unit tests for command dispatch in ladle.cli."""
from __future__ import annotations

import pytest

from ladle import cli, lint, make_pdf, ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def test_no_args_prints_usage_and_succeeds(capsys):
    assert cli.main([]) == 0
    assert "usage: ladle" in capsys.readouterr().out


def test_help_flag_succeeds(capsys):
    assert cli.main(["--help"]) == 0
    assert "usage: ladle" in capsys.readouterr().out


def test_version_flag(capsys):
    assert cli.main(["--version"]) == 0
    assert cli.__version__ in capsys.readouterr().out


def test_unknown_command_returns_2(capsys):
    assert cli.main(["frobnicate"]) == 2
    assert "unknown command" in capsys.readouterr().err


def test_known_command_delegates(monkeypatch):
    called = {}

    def fake_validate(argv):
        called["argv"] = argv
        return 7

    monkeypatch.setitem(cli.COMMANDS, "validate", fake_validate)
    # Global flags are stripped before dispatch; the command sees only its own.
    assert cli.main(["--quiet", "validate", "--book", "b.yaml"]) == 7
    assert called["argv"] == ["--book", "b.yaml"]


def test_global_flags_configure_console(monkeypatch):
    monkeypatch.setitem(cli.COMMANDS, "noop", lambda argv: 0)
    cli.main(["--no-color", "-v", "noop"])
    console = ui.get()
    assert console.color is False
    assert console.verbosity == 1


def test_missing_book_returns_exit_3(capsys):
    rc = cli.main(["validate", "--book", "/no/such/book.yaml"])
    assert rc == ui.NO_BOOK == 3
    err = capsys.readouterr().err
    assert "no book config found" in err
    assert "ladle new" in err            # the next-step hint


def test_unexpected_error_maps_to_1_without_debug(monkeypatch, capsys):
    def boom(argv):
        raise ValueError("kaboom")

    monkeypatch.setitem(cli.COMMANDS, "boom", boom)
    assert cli.main(["boom"]) == ui.ERROR
    assert "kaboom" in capsys.readouterr().err


def test_debug_reraises_for_tracebacks(monkeypatch):
    def boom(argv):
        raise ValueError("kaboom")

    monkeypatch.setitem(cli.COMMANDS, "boom", boom)
    with pytest.raises(ValueError, match="kaboom"):
        cli.main(["--debug", "boom"])


def test_subcommand_help_shows_examples(capsys):
    # argparse prints help to stdout and exits 0.
    with pytest.raises(SystemExit) as exc:
        lint.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "examples:" in out
    assert ui.REPO in out


def test_pdf_help_exits_cleanly_instead_of_building(capsys):
    # Regression: `ladle pdf --help` used to ignore argv and start a build.
    with pytest.raises(SystemExit) as exc:
        make_pdf.main(["--help"])
    assert exc.value.code == 0
    assert "usage:" in capsys.readouterr().out


def test_pdf_accepts_book_flag_from_build_chain(monkeypatch, tmp_path):
    # `ladle build --book X` threads --book into make_pdf; it must accept (ignore)
    # it and fail cleanly on the missing HTML, not argparse-error on --book.
    monkeypatch.setattr(make_pdf.config, "build_dir", lambda: tmp_path)  # empty -> no cookbook.html
    assert make_pdf.main(["--book", "any.yaml"]) == ui.ERROR
