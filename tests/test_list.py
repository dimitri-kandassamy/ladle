"""Unit tests for `ladle list` — the recipe-listing data command."""

from __future__ import annotations

import json

import pytest

from ladle import list_recipes, ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def _book(tmp_path, sections="[Savory, Desserts]"):
    (tmp_path / "recipes").mkdir(exist_ok=True)
    (tmp_path / "recipes" / "stew.md").write_text(
        "---\ntitle: Stew\ncategory: Savory\ntags: [hearty]\n---\n", encoding="utf-8"
    )
    (tmp_path / "recipes" / "cake.md").write_text(
        "---\ntitle: Cake\ncategory: Desserts\ndraft: true\n---\n", encoding="utf-8"
    )
    book = tmp_path / "book.yaml"
    book.write_text(f"title: T\nrecipes_dir: recipes\nsections: {sections}\n", encoding="utf-8")
    return book


def test_lists_all_recipes_in_book_order(tmp_path, capsys):
    book = _book(tmp_path)
    assert list_recipes.main(["--book", str(book)]) == ui.OK
    out = capsys.readouterr()
    assert out.err == ""  # data command: stdout only
    lines = out.out.strip().splitlines()
    # Savory before Desserts (section order), so Stew precedes Cake.
    assert lines[0].startswith("stew")
    assert lines[1].startswith("cake")
    assert "(draft)" in lines[1]


def test_json_shape(tmp_path, capsys):
    book = _book(tmp_path)
    ui.configure(json=True)
    list_recipes.main(["--book", str(book)])
    records = json.loads(capsys.readouterr().out)
    assert {r["slug"] for r in records} == {"stew", "cake"}
    assert next(r for r in records if r["slug"] == "cake")["draft"] is True


def test_category_filter(tmp_path, capsys):
    book = _book(tmp_path)
    ui.configure(plain=True)
    list_recipes.main(["--book", str(book), "--category", "Desserts"])
    rows = capsys.readouterr().out.strip().splitlines()
    assert len(rows) == 1
    assert rows[0].split("\t")[0] == "cake"


def test_tag_filter(tmp_path, capsys):
    book = _book(tmp_path)
    ui.configure(json=True)
    list_recipes.main(["--book", str(book), "--tag", "hearty"])
    records = json.loads(capsys.readouterr().out)
    assert [r["slug"] for r in records] == ["stew"]


def test_empty_book_exits_0_with_no_rows(tmp_path, capsys):
    (tmp_path / "recipes").mkdir()
    book = tmp_path / "book.yaml"
    book.write_text("title: T\nrecipes_dir: recipes\n", encoding="utf-8")
    assert list_recipes.main(["--book", str(book)]) == ui.OK
    assert capsys.readouterr().out.strip() == ""
