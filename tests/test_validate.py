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


def test_front_matter_is_empty_without_a_front_matter_block(tmp_path):
    """Used to raise IndexError, surfacing as `error: list index out of range`."""
    p = tmp_path / "r.md"
    p.write_text("## INGREDIENTS\n\n- salt\n", encoding="utf-8")
    assert validate.front_matter(p) == {}


def test_front_matter_is_empty_when_front_matter_is_unclosed(tmp_path):
    """validate reports a malformed recipe (see check_recipes); it must not abort on one."""
    p = tmp_path / "r.md"
    p.write_text("---\ntitle: X\n\n## INGREDIENTS\n\n- salt\n", encoding="utf-8")
    assert validate.front_matter(p) == {}
    assert validate.notes_line_count(p) == 0


def test_check_recipes_reports_unclosed_front_matter_per_file(tmp_path):
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "good.md").write_text("---\ntitle: Soup\ncategory: Savory\n---\n\n## NOTES\nfine\n", encoding="utf-8")
    (recipes / "unclosed.md").write_text("---\ntitle: X\n\n## NOTES\nnope\n", encoding="utf-8")

    results = {r["file"]: r for r in validate.check_recipes(recipes)}

    assert results["good.md"]["ok"] is True
    assert results["unclosed.md"]["ok"] is False
    assert "never closed" in results["unclosed.md"]["message"]


def test_validate_bodies_survives_an_unsplittable_recipe(tmp_path, capsys):
    """One malformed file must not abort the body check for every other recipe."""
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "unclosed.md").write_text("---\ntitle: X\n\n## NOTES\nnope\n", encoding="utf-8")
    (recipes / "good.md").write_text("---\ntitle: Soup\ncategory: Savory\n---\n\n## NOTES\nfine\n", encoding="utf-8")

    validate.failures.clear()
    validate.validate_bodies(recipes)

    assert "all body content was parsed" in capsys.readouterr().err


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


# ---- pdfinfo ---------------------------------------------------------------
def test_pdfinfo_parses_key_value_fields(tmp_path, monkeypatch):
    class Result:
        returncode = 0
        stdout = "Pages:          16\nPage size:      486 x 684 pts\n"

    monkeypatch.setattr(validate.subprocess, "run", lambda *a, **k: Result())

    info = validate._pdfinfo(tmp_path / "x.pdf")
    assert info["Pages"] == "16"
    assert info["Page size"] == "486 x 684 pts"  # only the first colon splits
    assert validate._pdf_page_count(tmp_path / "x.pdf") == 16


def test_pdfinfo_is_empty_when_poppler_is_missing(tmp_path, monkeypatch):
    """An absent binary raises FileNotFoundError; it does not return non-zero."""

    def boom(*args, **kwargs):
        raise FileNotFoundError(2, "No such file or directory", "pdfinfo")

    monkeypatch.setattr(validate.subprocess, "run", boom)

    assert validate._pdfinfo(tmp_path / "x.pdf") == {}
    assert validate._pdf_page_count(tmp_path / "x.pdf") == 0


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
    """A book whose one recipe uses a heading ladle does not know.

    A wrapped step used to belong here; it now renders correctly, so the
    remaining reportable case is structural — content that renders somewhere the
    author did not intend.
    """
    recipes = tmp_path / "recipes"
    recipes.mkdir()
    (recipes / "r.md").write_text(
        "---\ntitle: X\ncategory: Savory\n---\n\n## PREPARAÇÃO\nMexe-se tudo.\n",
        encoding="utf-8",
    )
    return recipes


def test_validate_bodies_notes_dropped_content_without_failing(tmp_path, capsys):
    validate.failures.clear()
    validate.validate_bodies(lossy_recipes(tmp_path))

    out = capsys.readouterr()
    assert out.out == ""  # stdout stays clean for piping
    assert "r.md:7:" in out.err  # file:line: message, so it's clickable
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


# ---- contact sheet: page-range split + sheet pagination --------------------


@pytest.mark.parametrize(
    "n_pages, workers, expected",
    [
        (0, 4, []),  # unknown count -> single whole-document render
        (1, 4, [(1, 1)]),
        (6, 4, [(1, 2), (3, 4), (5, 6)]),  # 6 pages, ceil(6/4)=2 each -> 3 slices
        (224, 4, [(1, 56), (57, 112), (113, 168), (169, 224)]),
    ],
)
def test_page_ranges_are_contiguous_and_cover_every_page(n_pages, workers, expected):
    ranges = validate._page_ranges(n_pages, workers)
    assert ranges == expected
    if n_pages > 0:
        assert ranges[0][0] == 1 and ranges[-1][1] == n_pages
        assert len(ranges) <= workers
        for (_, prev_last), (next_first, _) in zip(ranges, ranges[1:], strict=False):
            assert next_first == prev_last + 1  # no gaps, no overlaps


def _solid(n, size=(160, 225)):
    from PIL import Image

    return [Image.new("RGB", size, (i, i, i)) for i in range(n)]


def test_compose_sheets_paginates_and_bounds_height():
    per_sheet = validate.CONTACT_COLS * validate.CONTACT_ROWS_PER_SHEET
    # One full sheet + one leftover page -> two sheets, and no sheet is a giant strip.
    sheets = validate._compose_sheets(_solid(per_sheet + 1))
    assert len(sheets) == 2
    assert [s.size[1] for s in sheets]  # both have real height
    for s in sheets:
        assert s.size[1] < 16384  # under the canvas dimension that leaves it unopenable


def test_compose_sheets_single_page_is_one_sheet():
    sheets = validate._compose_sheets(_solid(1))
    assert len(sheets) == 1
