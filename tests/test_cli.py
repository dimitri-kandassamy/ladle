"""Unit tests for command dispatch in ladle.cli."""
from __future__ import annotations

from ladle import cli


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
    assert cli.main(["validate", "--book", "b.yaml"]) == 7
    assert called["argv"] == ["--book", "b.yaml"]
