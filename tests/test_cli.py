"""Unit tests for command dispatch in ladle.cli."""
from __future__ import annotations

import pytest

from ladle import cli, lint, make_pdf, ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def _cmd(fn):
    """Wrap a bare function as a registry Command for monkeypatching COMMANDS."""
    return cli.Command(fn, "test command", "Inspect & validate")


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

    monkeypatch.setitem(cli.COMMANDS, "validate", _cmd(fake_validate))
    # Global flags are stripped before dispatch; the command sees only its own.
    assert cli.main(["--quiet", "validate", "--book", "b.yaml"]) == 7
    assert called["argv"] == ["--book", "b.yaml"]


def test_global_flags_configure_console(monkeypatch):
    monkeypatch.setitem(cli.COMMANDS, "noop", _cmd(lambda argv: 0))
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

    monkeypatch.setitem(cli.COMMANDS, "boom", _cmd(boom))
    assert cli.main(["boom"]) == ui.ERROR
    assert "kaboom" in capsys.readouterr().err


def test_debug_reraises_for_tracebacks(monkeypatch):
    def boom(argv):
        raise ValueError("kaboom")

    monkeypatch.setitem(cli.COMMANDS, "boom", _cmd(boom))
    with pytest.raises(ValueError, match="kaboom"):
        cli.main(["--debug", "boom"])


def test_help_lists_every_registered_command(capsys):
    # Guards against drift: generated help must mention every command.
    cli.main(["--help"])
    out = capsys.readouterr().out
    for name in cli.COMMANDS:
        assert name in out


def test_subcommand_bad_flag_returns_2_not_raises(capsys):
    # A subcommand argparse error becomes a returned exit code, not a SystemExit.
    assert cli.main(["list", "--bogus"]) == ui.USAGE
    assert "unrecognized arguments" in capsys.readouterr().err


def test_build_help_returns_0_through_dispatch(capsys):
    assert cli.main(["build", "--help"]) == ui.OK
    assert "usage:" in capsys.readouterr().out


def test_help_command_shows_subcommand_help(capsys):
    assert cli.main(["help", "lint"]) == ui.OK
    assert "examples:" in capsys.readouterr().out


def test_keyboard_interrupt_maps_to_130(monkeypatch):
    def interrupt(argv):
        raise KeyboardInterrupt

    monkeypatch.setitem(cli.COMMANDS, "hang", _cmd(interrupt))
    assert cli.main(["hang"]) == ui.INTERRUPTED == 130


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
