"""Unit tests for the pure parsing helpers in ladle.validate."""

from __future__ import annotations

import pytest

from ladle import ui, validate


@pytest.fixture(autouse=True)
def _reset_console():
    ui.configure(color=False)
    yield
    ui.configure()


def test_front_matter_reads_yaml_block(tmp_path):
    p = tmp_path / "r.md"
    p.write_text("---\ntitle: Soup\ndraft: true\n---\n\nbody\n", encoding="utf-8")
    assert validate.front_matter(p) == {"title": "Soup", "draft": True}


def test_notes_line_count_counts_non_empty_lines_under_notes(tmp_path):
    p = tmp_path / "r.md"
    p.write_text(
        "---\ntitle: X\n---\n"
        "## INGREDIENTS\n- salt\n"
        "## NOTES\n"
        "first note\n"
        "\n"
        "second note\n"
        "## DIRECTIONS\n1. stop counting here\n",
        encoding="utf-8",
    )
    assert validate.notes_line_count(p) == 2


def test_notes_line_count_zero_without_notes_section(tmp_path):
    p = tmp_path / "r.md"
    p.write_text("---\ntitle: X\n---\n## INGREDIENTS\n- salt\n", encoding="utf-8")
    assert validate.notes_line_count(p) == 0


def test_notes_line_count_is_case_insensitive(tmp_path):
    p = tmp_path / "r.md"
    p.write_text("## Notes\nonly line\n", encoding="utf-8")
    assert validate.notes_line_count(p) == 1


# ---- report routing (T1: stderr + gated color) -----------------------------
def test_validate_recipes_reports_to_stderr_without_ansi(tmp_path, capsys):
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "bad.md").write_text("no front matter here\n", encoding="utf-8")

    validate.failures.clear()
    validate.validate_recipes(recipes)

    out = capsys.readouterr()
    assert out.out == ""  # nothing on stdout (the data channel)
    assert "FAIL" in out.err  # the diagnostic is on stderr
    assert "\033" not in out.err  # color off -> no raw ANSI
    assert validate.failures  # the bad recipe was recorded


# ---- recipe body -----------------------------------------------------------
def lossy_recipes(tmp_path):
    """A book whose one recipe has a step wrapped onto a second line."""
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "r.md").write_text(
        "---\ntitle: X\ncategory: Savory\n---\n\n## DIRECTIONS\n1. Beat the butter,\nthen fold in the flour.\n",
        encoding="utf-8",
    )
    return recipes


def test_validate_bodies_notes_dropped_content_without_failing(tmp_path, capsys):
    validate.failures.clear()
    validate.validate_bodies(lossy_recipes(tmp_path))

    out = capsys.readouterr()
    assert out.out == ""  # stdout stays clean for piping
    assert "r.md:8:" in out.err  # file:line: message, so it's clickable
    assert "will not appear in the book" in out.err
    assert "--strict" in out.err  # tells the user how to escalate
    assert not validate.failures  # a note by default, not a failure


def test_validate_bodies_fails_under_strict(tmp_path, capsys):
    validate.failures.clear()
    validate.validate_bodies(lossy_recipes(tmp_path), strict=True)

    assert "FAIL" in capsys.readouterr().err
    assert len(validate.failures) == 1


def test_validate_bodies_reports_ok_on_a_clean_book(tmp_path, capsys):
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "r.md").write_text(
        "---\ntitle: X\ncategory: Savory\n---\n\n## DIRECTIONS\n1. Beat the butter.\n", encoding="utf-8"
    )
    validate.failures.clear()
    validate.validate_bodies(recipes, strict=True)

    assert "ok" in capsys.readouterr().err
    assert not validate.failures


def test_validate_strict_flag_turns_dropped_content_into_exit_4(tmp_path, monkeypatch):
    book = tmp_path / "book.yaml"
    book.write_text("title: X\nrecipes_dir: recipes\n", encoding="utf-8")
    lossy_recipes(tmp_path)
    monkeypatch.setattr(validate, "BUILD", tmp_path / "build")

    # Without --strict the body content is only a note, so the *only* failures
    # are the missing build artifacts; with it, the dropped step fails too.
    monkeypatch.setattr(validate, "contact_sheet", lambda: None)
    lenient = validate.main(["--book", str(book)])
    n_lenient = len(validate.failures)
    strict = validate.main(["--book", str(book), "--strict"])
    assert lenient == strict == ui.VALIDATION
    assert len(validate.failures) == n_lenient + 1


def test_validate_main_returns_exit_4_on_failure(tmp_path, monkeypatch):
    book = tmp_path / "book.yaml"
    book.write_text("title: X\nrecipes_dir: recipes\n", encoding="utf-8")
    (tmp_path / "recipes").mkdir()
    (tmp_path / "recipes" / "bad.md").write_text("no front matter\n", encoding="utf-8")
    monkeypatch.setattr(validate, "BUILD", tmp_path / "build")  # empty -> pdf/epub missing
    assert validate.main(["--book", str(book)]) == ui.VALIDATION == 4
