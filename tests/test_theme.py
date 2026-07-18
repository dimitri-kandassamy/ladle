"""Unit tests for `ladle theme lint` and `ladle theme preview` (theme.py)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from ladle import config, theme


def _levels(results: list[dict]) -> list[str]:
    return [r["level"] for r in results]


def _fails(results: list[dict]) -> list[str]:
    return [r["message"] for r in results if r["level"] == "fail"]


# ---- the bundled default theme is the reference: it must lint clean ---------
def test_lint_default_theme_passes():
    results = theme.lint(config.THEMES_DIR / "default")
    assert _fails(results) == []
    assert "fail" not in _levels(results)


# ---- manifest --------------------------------------------------------------
def test_check_manifest_missing_file(tmp_path):
    manifest, results = theme.check_manifest(tmp_path)
    assert manifest is None
    assert "theme.yaml not found" in _fails(results)[0]


def test_check_manifest_schema_violation(tmp_path):
    # `name` is required by theme.schema.json; omitting it is a hard fail.
    (tmp_path / "theme.yaml").write_text("title: No Name Here\n", encoding="utf-8")
    manifest, results = theme.check_manifest(tmp_path)
    assert manifest is None
    assert results[0]["level"] == "fail"


def test_check_manifest_valid(tmp_path):
    (tmp_path / "theme.yaml").write_text("name: mini\n", encoding="utf-8")
    manifest, results = theme.check_manifest(tmp_path)
    assert manifest is not None and manifest["name"] == "mini"
    assert _levels(results) == ["ok"]


# ---- templates -------------------------------------------------------------
def test_check_templates_missing_both(tmp_path):
    results = theme.check_templates(tmp_path)  # no templates/ dir at all
    assert len(_fails(results)) == 2


def test_check_templates_syntax_error(tmp_path):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    (tdir / "print.html.j2").write_text("{{ oops %}", encoding="utf-8")
    (tdir / "epub.html.j2").write_text("<p>{{ book.title }}</p>", encoding="utf-8")
    results = theme.check_templates(tmp_path)
    fails = _fails(results)
    assert len(fails) == 1
    assert "print.html.j2" in fails[0]


def test_check_templates_all_present(tmp_path):
    tdir = tmp_path / "templates"
    tdir.mkdir()
    for name in theme.REQUIRED_TEMPLATES:
        (tdir / name).write_text("<p>{{ book.title }}</p>", encoding="utf-8")
    assert _fails(theme.check_templates(tmp_path)) == []


# ---- fonts -----------------------------------------------------------------
def _font_theme(tmp_path: Path, license_str: str, *, with_meta: bool = True, drop_file: bool = False) -> dict:
    fonts = tmp_path / "fonts"
    fonts.mkdir()
    if not drop_file:
        (fonts / "F.ttf").write_bytes(b"\x00")
    manifest = {"font_faces": [{"family": "Fam", "file": "F.ttf", "style": "normal"}]}
    if with_meta:
        manifest["fonts_meta"] = [{"family": "Fam", "license": license_str}]
    return manifest


def test_check_fonts_permissible_license(tmp_path):
    manifest = _font_theme(tmp_path, "OFL-1.1")
    assert _fails(theme.check_fonts(tmp_path, manifest)) == []


def test_check_fonts_apache_and_ufl_accepted(tmp_path):
    assert theme._license_permissible("Apache-2.0")
    assert theme._license_permissible("SIL Open Font License 1.1")
    assert theme._license_permissible("UFL-1.0")
    assert not theme._license_permissible("Proprietary-EULA")
    assert not theme._license_permissible("")


def test_check_fonts_non_permissible_license(tmp_path):
    manifest = _font_theme(tmp_path, "Proprietary-EULA")
    fails = _fails(theme.check_fonts(tmp_path, manifest))
    assert len(fails) == 1 and "not on the permissible allowlist" in fails[0]


def test_check_fonts_missing_meta_entry(tmp_path):
    manifest = _font_theme(tmp_path, "OFL-1.1", with_meta=False)
    fails = _fails(theme.check_fonts(tmp_path, manifest))
    assert len(fails) == 1 and "no fonts_meta license entry" in fails[0]


def test_check_fonts_missing_file(tmp_path):
    manifest = _font_theme(tmp_path, "OFL-1.1", drop_file=True)
    fails = _fails(theme.check_fonts(tmp_path, manifest))
    assert any("not found" in m for m in fails)


def test_check_fonts_no_fonts_is_a_note_not_a_failure(tmp_path):
    results = theme.check_fonts(tmp_path, {})
    assert _levels(results) == ["note"]


# ---- command dispatch ------------------------------------------------------
def test_main_lint_default_ok():
    assert theme.main(["lint", "default"]) == 0


def test_main_unknown_subcommand_is_usage_error():
    assert theme.main(["frobnicate"]) == 2  # ui.USAGE


def test_main_no_args_prints_group_help():
    assert theme.main([]) == 0


def test_lint_missing_theme_dir_errors():
    assert theme._lint_main(["/no/such/theme/dir"]) == 1  # ui.ERROR


# ---- the canonical sample book must stay buildable --------------------------
def test_sample_book_is_a_valid_book_config():
    # `theme preview` renders this; if it stops validating, previews break.
    book = config.load_book_config(str(config.SAMPLE_BOOK))
    assert book.data["title"]
    recipes = sorted(book.recipes_dir.glob("*.md"))
    assert len(recipes) >= 3


# ---- theme preview ---------------------------------------------------------
def test_write_preview_book_overrides_theme_and_absolutizes_paths(tmp_path):
    theme_dir = config.THEMES_DIR / "default"
    out = theme._write_preview_book(config.SAMPLE_BOOK, theme_dir, tmp_path)
    data = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert data["theme"] == str(theme_dir.resolve())
    assert Path(data["recipes_dir"]) == (config.SAMPLE_BOOK.parent / "recipes").resolve()
    assert Path(data["introduction"]).is_absolute()
    assert Path(data["introduction"]).name == "introduction.md"


def test_preview_missing_book_raises_no_book_error(tmp_path):
    with pytest.raises(config.NoBookError):
        theme.preview(config.THEMES_DIR / "default", str(tmp_path / "nope.yaml"))


def test_preview_main_missing_theme_dir_errors():
    assert theme._preview_main(["/no/such/theme/dir"]) == 1  # ui.ERROR


def test_rasterize_preview_skips_without_poppler(tmp_path, monkeypatch):
    import shutil

    monkeypatch.setattr(shutil, "which", lambda name: None)
    assert theme._rasterize_preview(tmp_path / "cookbook.pdf", tmp_path) == []


# The full `theme preview` render (WeasyPrint + poppler) is exercised end-to-end
# by the CI `build` job, not here, to keep the unit suite fast.
