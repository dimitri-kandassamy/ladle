"""Unit tests for `ladle theme lint` (theme.py)."""

from __future__ import annotations

from pathlib import Path

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
