"""Unit tests for `ladle lint` — the data command split out of validate."""
from __future__ import annotations

import json

import pytest

from ladle import lint, ui


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure()
    yield
    ui.configure()


def _book(tmp_path, *recipes: tuple[str, str]):
    """Write a book.yaml + recipes/*.md; return the book.yaml path."""
    (tmp_path / "recipes").mkdir(exist_ok=True)
    for name, text in recipes:
        (tmp_path / "recipes" / name).write_text(text, encoding="utf-8")
    book = tmp_path / "book.yaml"
    book.write_text("title: T\nrecipes_dir: recipes\n", encoding="utf-8")
    return book


VALID = "---\ntitle: Soup\ncategory: Savory\n---\n\n## INGREDIENTS\n- salt\n"
BAD = "---\ntitle: Soup\n---\n\nno category (schema requires it)\n"


def test_clean_book_exits_0(tmp_path, capsys):
    book = _book(tmp_path, ("soup.md", VALID))
    assert lint.main(["--book", str(book)]) == ui.OK
    out = capsys.readouterr()
    assert "ok    soup.md" in out.out
    assert out.err == ""                    # data command: everything on stdout


def test_schema_error_exits_4(tmp_path, capsys):
    book = _book(tmp_path, ("soup.md", BAD))
    assert lint.main(["--book", str(book)]) == ui.VALIDATION == 4
    assert "error" in capsys.readouterr().out


def test_json_output_parses_and_is_clean(tmp_path, capsys):
    book = _book(tmp_path, ("ok.md", VALID), ("bad.md", BAD))
    ui.configure(json=True)
    rc = lint.main(["--book", str(book)])
    out = capsys.readouterr()
    assert rc == ui.VALIDATION
    assert "\033" not in out.out            # no ANSI contaminating the JSON channel
    records = json.loads(out.out)           # stdout is valid JSON
    by_file = {r["file"]: r for r in records}
    assert by_file["ok.md"]["ok"] is True
    assert by_file["bad.md"]["ok"] is False


def test_plain_output_is_tab_separated(tmp_path, capsys):
    book = _book(tmp_path, ("soup.md", VALID))
    ui.configure(plain=True)
    lint.main(["--book", str(book)])
    row = capsys.readouterr().out.strip()
    assert row.split("\t")[:2] == ["soup.md", "ok"]
