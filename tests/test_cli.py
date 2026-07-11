"""Unit tests for command dispatch in ladle.cli."""

from __future__ import annotations

import pytest

from ladle import cli, make_pdf, ui, validate


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def _cmd(fn):
    """Wrap a bare function as a registry Command for monkeypatching COMMANDS."""
    return cli.Command(fn, "test command")


def test_no_args_prints_help_and_succeeds(capsys):
    assert cli.main([]) == 0
    assert "USAGE" in capsys.readouterr().out


def test_help_flag_succeeds(capsys):
    assert cli.main(["--help"]) == 0
    assert "USAGE" in capsys.readouterr().out


def test_help_layout(capsys):
    cli.main(["--help"])
    out = capsys.readouterr().out
    lines = out.splitlines()
    # Description is the sole top line — no program name / version.
    assert lines[0] == "build cookbooks (PDF + EPUB) from markdown."
    assert cli.__version__ not in out
    # All four headings present, uppercase, no trailing colon.
    for heading in ("USAGE", "COMMANDS", "GLOBAL FLAGS", "EXAMPLES"):
        assert heading in lines
        assert f"{heading}:" not in out
    # --version is documented as a global flag.
    assert any("--version" in line for line in lines)


def test_version_flag(capsys):
    assert cli.main(["--version"]) == 0
    assert cli.__version__ in capsys.readouterr().out


def test_version_short_flag(capsys):
    assert cli.main(["-V"]) == 0
    assert cli.__version__ in capsys.readouterr().out


def test_version_is_top_level_only(capsys):
    # #6: --version/-V is a top-level action (like git/cargo/pip) — it prints
    # before a command, but is not accepted after one.
    assert cli.main(["--version", "build"]) == 0  # consumed at the top level
    assert cli.__version__ in capsys.readouterr().out
    assert cli.main(["build", "--version"]) == ui.USAGE  # unknown flag to `build`
    assert "unrecognized arguments" in capsys.readouterr().err


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


def test_color_flag_forces_color_on(monkeypatch):
    # #8: --color forces color on (the counterpart to --no-color); absent -> auto.
    monkeypatch.setitem(cli.COMMANDS, "noop", _cmd(lambda argv: 0))
    cli.main(["--color", "noop"])
    assert ui.get().color is True
    cli.main(["noop"])
    assert ui.get().color is None


def test_missing_book_returns_exit_3(capsys):
    rc = cli.main(["validate", "--book", "/no/such/book.yaml"])
    assert rc == ui.NO_BOOK == 3
    err = capsys.readouterr().err
    assert "no book config found" in err
    assert "ladle new" in err  # the next-step hint


def test_missing_title_returns_clean_error_not_traceback(capsys, tmp_path):
    # QA #1: a book.yaml missing `title` fails with a one-line message, no KeyError.
    book = tmp_path / "book.yaml"
    book.write_text("language: en\n", encoding="utf-8")
    rc = cli.main(["build", "--book", str(book)])
    assert rc == ui.ERROR
    err = capsys.readouterr().err
    assert "missing required field: title" in err
    assert "Traceback" not in err


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
    assert cli.main(["validate", "--bogus"]) == ui.USAGE
    assert "unrecognized arguments" in capsys.readouterr().err


def test_build_help_returns_0_through_dispatch(capsys):
    assert cli.main(["build", "--help"]) == ui.OK
    assert "usage:" in capsys.readouterr().out


def test_help_command_shows_subcommand_help(capsys):
    assert cli.main(["help", "validate"]) == ui.OK
    assert "examples:" in capsys.readouterr().out


def test_keyboard_interrupt_maps_to_130(monkeypatch):
    def interrupt(argv):
        raise KeyboardInterrupt

    monkeypatch.setitem(cli.COMMANDS, "hang", _cmd(interrupt))
    assert cli.main(["hang"]) == ui.INTERRUPTED == 130


def test_subcommand_help_shows_examples(capsys):
    # argparse prints help to stdout and exits 0.
    with pytest.raises(SystemExit) as exc:
        validate.main(["--help"])
    assert exc.value.code == 0
    out = capsys.readouterr().out
    assert "examples:" in out
    assert ui.REPO in out


def test_subcommand_help_uses_ladle_prog_name(capsys):
    # QA #6: usage must read `ladle <sub>`, not argparse's argv[0] (`__main__.py`).
    with pytest.raises(SystemExit):
        validate.main(["--help"])
    out = capsys.readouterr().out
    assert "usage: ladle validate" in out
    assert "__main__" not in out


def test_pdf_render_fails_cleanly_without_html(monkeypatch, tmp_path):
    # The internal pdf stage errors cleanly when build/cookbook.html is missing.
    monkeypatch.setattr(make_pdf.config, "build_dir", lambda: tmp_path)  # empty -> no cookbook.html
    assert make_pdf.render() == ui.ERROR
