"""Unit tests for path resolution and theme/colour helpers in ladle.config."""
from __future__ import annotations

from pathlib import Path

from ladle import config
from ladle.config import BookConfig


def test_hex_to_rgb_with_hash():
    assert config.hex_to_rgb("#16203a") == (22, 32, 58)


def test_hex_to_rgb_without_hash():
    assert config.hex_to_rgb("faefdb") == (250, 239, 219)


def test_load_theme_missing_manifest_returns_defaults(tmp_path):
    # A theme dir without a theme.yaml still yields the normalized shape.
    theme = config.load_theme(tmp_path)
    assert theme == {"name": "", "palette": {}, "fonts": {}, "font_faces": []}


def test_load_theme_merges_manifest_over_defaults(tmp_path):
    (tmp_path / "theme.yaml").write_text(
        "name: midnight\npalette:\n  navy: '#000'\n", encoding="utf-8"
    )
    theme = config.load_theme(tmp_path)
    assert theme["name"] == "midnight"
    assert theme["palette"] == {"navy": "#000"}
    # keys absent from the manifest still fall back to the defaults
    assert theme["font_faces"] == []


def _book(data: dict, path: str = "/books/demo/book.yaml") -> BookConfig:
    return BookConfig(path=Path(path), data=data)


def test_bookconfig_root_is_yaml_dir():
    assert _book({}).root == Path("/books/demo")


def test_bookconfig_default_content_paths():
    cfg = _book({})
    assert cfg.recipes_dir == Path("/books/demo/recipes")
    assert cfg.introduction_path == Path("/books/demo/content/introduction.md")


def test_bookconfig_content_paths_are_overridable():
    cfg = _book({"recipes_dir": "src/recipes", "introduction": "intro.md"})
    assert cfg.recipes_dir == Path("/books/demo/src/recipes")
    assert cfg.introduction_path == Path("/books/demo/intro.md")


def test_theme_dir_bare_name_resolves_into_package():
    # A bare `theme: default` points at a theme shipped inside the package.
    assert _book({"theme": "default"}).theme_dir == config.THEMES_DIR / "default"


def test_theme_dir_defaults_to_default_theme():
    assert _book({}).theme_dir == config.THEMES_DIR / "default"


def test_theme_dir_relative_path_resolves_against_book():
    cfg = _book({"theme": "themes/mine"})
    assert cfg.theme_dir == Path("/books/demo/themes/mine")


def test_theme_dir_absolute_path_is_left_as_is():
    cfg = _book({"theme": "/opt/themes/mine"})
    assert cfg.theme_dir == Path("/opt/themes/mine")


def test_theme_path_joins_under_theme_dir():
    cfg = _book({"theme": "default"})
    assert cfg.theme_path("css", "print.css") == config.THEMES_DIR / "default/css/print.css"


def test_resolve_book_path_prefers_cli_value(monkeypatch):
    monkeypatch.setenv("BOOK_CONFIG", "from-env.yaml")
    assert config.resolve_book_path("from-cli.yaml") == Path("from-cli.yaml").resolve()


def test_resolve_book_path_falls_back_to_env(monkeypatch):
    monkeypatch.setenv("BOOK_CONFIG", "from-env.yaml")
    assert config.resolve_book_path(None) == Path("from-env.yaml").resolve()


def test_resolve_book_path_defaults_to_cwd_book_yaml(monkeypatch):
    monkeypatch.delenv("BOOK_CONFIG", raising=False)
    assert config.resolve_book_path(None) == Path("book.yaml").resolve()


def test_build_dir_honours_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("LADLE_BUILD", str(tmp_path / "out"))
    assert config.build_dir() == (tmp_path / "out").resolve()


def test_rel_returns_relative_when_under_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    assert config.rel(tmp_path / "build" / "cookbook.pdf") == "build/cookbook.pdf"


def test_rel_returns_absolute_when_outside_cwd(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    other = Path("/somewhere/else/file.txt")
    assert config.rel(other) == str(other)


def test_load_book_config_reads_yaml(tmp_path):
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\ntheme: default\n", encoding="utf-8")
    cfg = config.load_book_config(str(book))
    assert cfg.data["title"] == "Demo"
    assert cfg.root == tmp_path


def test_load_book_config_empty_file_yields_empty_data(tmp_path):
    book = tmp_path / "book.yaml"
    book.write_text("", encoding="utf-8")
    assert config.load_book_config(str(book)).data == {}
