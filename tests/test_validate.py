"""Unit tests for the pure parsing helpers in ladle.validate."""
from __future__ import annotations

from ladle import validate


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
