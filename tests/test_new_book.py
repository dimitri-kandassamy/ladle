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
    rc = new_book.main(
        ["--name", "pt", "--title", "Título", "--subtitle", "Sub", "--language", "pt"]
    )
    assert rc == 0
    book_dir = tmp_path / "books" / "pt"
    assert (book_dir / "book.yaml").exists()
    assert (book_dir / "content" / "introduction.md").exists()
    assert (book_dir / "recipes" / "_example-recipe.md").exists()

    data = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))
    assert data["title"] == "Título"
    assert data["language"] == "pt"
    assert data["theme"] == "default"


def test_palette_overrides_are_applied(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    new_book.main(
        ["--name", "pt", "--title", "T", "--subtitle", "S", "--language", "pt",
         "--palette-navy", "#010203", "--palette-cream", "#fefefe"]
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
