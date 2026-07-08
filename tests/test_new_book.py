"""Unit tests for the `ladle new` scaffolder."""

from __future__ import annotations

import pytest
import yaml

from ladle import new_book, ui

# Every non-interactive field supplied, so main() never falls back to input().
FULL = ["--title", "T", "--subtitle", "S", "--language", "en"]


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def test_rejects_invalid_slug(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["--name", "Bad Name"]) == ui.USAGE == 2
    assert "must match" in capsys.readouterr().err
    assert not (tmp_path / "books").exists()


def test_scaffolds_a_runnable_book(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    rc = new_book.main(["--name", "pt", "--title", "Título", "--subtitle", "Sub", "--language", "pt"])
    assert rc == 0
    book_dir = tmp_path / "books" / "pt"
    assert (book_dir / "book.yaml").exists()
    assert (book_dir / "content" / "introduction.md").exists()
    recipe = book_dir / "recipes" / "example-recipe.md"
    assert recipe.exists()

    data = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))
    assert data["title"] == "Título"
    assert data["language"] == "pt"
    assert data["theme"] == "default"


def test_first_build_is_not_empty(tmp_path, monkeypatch):
    # Activation guarantee: `new` then `build` must yield a populated book, not a
    # blank Contents page. The example recipe ships non-draft, and its referenced
    # illustration exists on disk (no missing-asset warning on the first build).
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["--name", "pt", *FULL]) == 0
    book_dir = tmp_path / "books" / "pt"

    fm = yaml.safe_load((book_dir / "recipes" / "example-recipe.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["draft"] is False

    illustration = book_dir / fm["illustration"]
    assert illustration.exists()
    assert illustration.read_text(encoding="utf-8").lstrip().startswith("<svg")


def test_palette_overrides_are_applied(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    new_book.main(
        [
            "--name",
            "pt",
            "--title",
            "T",
            "--subtitle",
            "S",
            "--language",
            "pt",
            "--palette-navy",
            "#010203",
            "--palette-cream",
            "#fefefe",
        ]
    )
    data = yaml.safe_load((tmp_path / "books" / "pt" / "book.yaml").read_text(encoding="utf-8"))
    assert data["palette"]["navy"] == "#010203"
    assert data["palette"]["cream"] == "#fefefe"


def test_refuses_to_overwrite_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["--name", "pt", *FULL]) == 0
    capsys.readouterr()
    assert new_book.main(["--name", "pt", *FULL]) == 1
    assert "already exists" in capsys.readouterr().err


def test_force_allows_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["--name", "pt", *FULL]) == 0
    assert new_book.main(["--name", "pt", "--force", *FULL]) == 0


def test_name_only_uses_defaults_without_prompting(tmp_path, monkeypatch):
    # Non-interactive (pytest stdin isn't a TTY): must NOT call input() and hang;
    # the omitted fields fall back to their defaults.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("prompted in non-interactive mode"))
    assert new_book.main(["--name", "pt"]) == 0
    data = yaml.safe_load((tmp_path / "books" / "pt" / "book.yaml").read_text(encoding="utf-8"))
    assert data["language"] == "en"  # the default
    assert data["title"] == "The Pt Cookbook"  # default derived from name


def test_missing_name_fails_fast_when_noninteractive(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("prompted in non-interactive mode"))
    assert new_book.main([]) == ui.USAGE == 2
    assert "--name is required" in capsys.readouterr().err
