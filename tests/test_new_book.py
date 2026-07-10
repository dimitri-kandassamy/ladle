"""Unit tests for the `ladle new` scaffolder."""

from __future__ import annotations

import pytest
import yaml

from ladle import new_book, ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def test_name_used_verbatim_including_spaces(tmp_path, monkeypatch):
    # The name is the directory, as typed — no slugifying, no case-folding.
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["My Cookbook"]) == 0
    book_dir = tmp_path / "My Cookbook"
    assert book_dir.exists()
    data = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))
    assert data["title"] == "My Cookbook"


def test_unicode_and_non_latin_names_are_kept(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["Café"]) == 0
    assert (tmp_path / "Café").exists()  # accent preserved in the path
    assert new_book.main(["日本料理"]) == 0
    assert (tmp_path / "日本料理").exists()  # non-Latin scripts work too


def test_rejects_path_unsafe_names(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["a/b"]) == ui.USAGE == 2
    assert "may not contain" in capsys.readouterr().err
    assert new_book.main([".."]) == ui.USAGE == 2
    assert not (tmp_path / "a").exists()


def test_scaffolds_a_runnable_book(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["pt", "--title", "Título", "--language", "pt"]) == 0
    book_dir = tmp_path / "pt"
    assert (book_dir / "book.yaml").exists()
    assert (book_dir / "content" / "introduction.md").exists()
    assert (book_dir / "recipes" / "example-recipe.md").exists()

    data = yaml.safe_load((book_dir / "book.yaml").read_text(encoding="utf-8"))
    assert data["title"] == "Título"
    assert data["language"] == "pt"
    # Minimal book.yaml: theme/palette/fonts are NOT written — they fall back to
    # the theme, so a fresh book stays free of redundant defaults.
    assert "theme" not in data
    assert "palette" not in data
    assert "fonts" not in data


def test_name_defaults_to_book(tmp_path, monkeypatch):
    # Zero-arg: `ladle new` scaffolds ./book/ with default title/language, no prompt.
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("builtins.input", lambda *a: pytest.fail("new must never prompt"))
    assert new_book.main([]) == 0
    data = yaml.safe_load((tmp_path / "book" / "book.yaml").read_text(encoding="utf-8"))
    assert data["title"] == "Book"  # derived from the default name
    assert data["language"] == "en"


def test_title_defaults_from_name(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["my-cookbook"]) == 0
    data = yaml.safe_load((tmp_path / "my-cookbook" / "book.yaml").read_text(encoding="utf-8"))
    assert data["title"] == "My Cookbook"  # hyphens -> spaces, Title Case


def test_first_build_is_not_empty(tmp_path, monkeypatch):
    # Activation guarantee: `new` then `build` must yield a populated book, not a
    # blank Contents page. The example recipe ships non-draft, and its referenced
    # illustration exists on disk (no missing-asset warning on the first build).
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["pt"]) == 0
    book_dir = tmp_path / "pt"

    fm = yaml.safe_load((book_dir / "recipes" / "example-recipe.md").read_text(encoding="utf-8").split("---")[1])
    assert fm["draft"] is False

    illustration = book_dir / fm["illustration"]
    assert illustration.exists()
    assert illustration.read_text(encoding="utf-8").lstrip().startswith("<svg")


def test_refuses_to_overwrite_without_force(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["pt"]) == 0
    capsys.readouterr()
    assert new_book.main(["pt"]) == 1
    assert "already exists" in capsys.readouterr().err


def test_force_allows_overwrite(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert new_book.main(["pt"]) == 0
    assert new_book.main(["pt", "--force"]) == 0
