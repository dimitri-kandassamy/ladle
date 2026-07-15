"""Unit tests for path resolution and theme/colour helpers in ladle.config."""

from __future__ import annotations

from pathlib import Path

import pytest

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
    (tmp_path / "theme.yaml").write_text("name: midnight\npalette:\n  navy: '#000'\n", encoding="utf-8")
    theme = config.load_theme(tmp_path)
    assert theme["name"] == "midnight"
    assert theme["palette"] == {"navy": "#000"}
    # keys absent from the manifest still fall back to the defaults
    assert theme["font_faces"] == []


def _book(data: dict, path: str = "/tmp/demo/book.yaml") -> BookConfig:
    return BookConfig(path=Path(path), data=data)


def test_bookconfig_root_is_yaml_dir():
    assert _book({}).root == Path("/tmp/demo")


def test_bookconfig_default_content_paths():
    cfg = _book({})
    assert cfg.recipes_dir == Path("/tmp/demo/recipes")
    assert cfg.introduction_path == Path("/tmp/demo/content/introduction.md")


def test_bookconfig_content_paths_are_overridable():
    cfg = _book({"recipes_dir": "src/recipes", "introduction": "intro.md"})
    assert cfg.recipes_dir == Path("/tmp/demo/src/recipes")
    assert cfg.introduction_path == Path("/tmp/demo/intro.md")


def test_theme_dir_bare_name_resolves_into_package():
    # A bare `theme: default` points at a theme shipped inside the package.
    assert _book({"theme": "default"}).theme_dir == config.THEMES_DIR / "default"


def test_theme_dir_defaults_to_default_theme():
    assert _book({}).theme_dir == config.THEMES_DIR / "default"


def test_theme_dir_relative_path_resolves_against_book():
    cfg = _book({"theme": "themes/mine"})
    assert cfg.theme_dir == Path("/tmp/demo/themes/mine")


def test_theme_dir_absolute_path_is_left_as_is():
    cfg = _book({"theme": "/opt/themes/mine"})
    assert cfg.theme_dir == Path("/opt/themes/mine")


def test_theme_path_joins_under_theme_dir():
    cfg = _book({"theme": "default"})
    assert cfg.theme_path("css", "print.css") == config.THEMES_DIR / "default/css/print.css"


def test_resolve_book_path_prefers_cli_value():
    assert config.resolve_book_path("from-cli.yaml") == Path("from-cli.yaml").resolve()


def test_resolve_book_path_ignores_book_config_env(monkeypatch):
    # #16: $BOOK_CONFIG was dropped — it must no longer affect resolution.
    monkeypatch.setenv("BOOK_CONFIG", "from-env.yaml")
    assert config.resolve_book_path(None) == Path("book.yaml").resolve()


def test_resolve_book_path_defaults_to_cwd_book_yaml():
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


def test_load_book_config_empty_file_raises_missing_title(tmp_path):
    # B1: an empty book.yaml is a valid mapping but has no `title` — the schema
    # now fails it at load with a clear message, not deeper in the build.
    book = tmp_path / "book.yaml"
    book.write_text("", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="'title' is a required property"):
        config.load_book_config(str(book))


def test_load_book_config_missing_file_raises_no_book_error(tmp_path):
    with pytest.raises(config.NoBookError):
        config.load_book_config(str(tmp_path / "does-not-exist.yaml"))


def test_load_book_config_malformed_yaml_raises_config_error(tmp_path):
    # QA #1: a YAML syntax error becomes a clean ConfigError, not a raw traceback.
    book = tmp_path / "book.yaml"
    book.write_text('title: "unterminated\nbad: [1, 2\n', encoding="utf-8")
    with pytest.raises(config.ConfigError, match="invalid YAML"):
        config.load_book_config(str(book))


def test_load_book_config_non_mapping_raises_config_error(tmp_path):
    # A top-level list/scalar isn't a book config.
    book = tmp_path / "book.yaml"
    book.write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="must be a mapping"):
        config.load_book_config(str(book))


# ---- B1: book.yaml schema validation ---------------------------------------


def test_load_book_config_unknown_key_raises_config_error(tmp_path):
    # A typo'd key (`recipes` for `recipes_dir`) is caught, not silently ignored.
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\nrecipes: recipes\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="recipes"):
        config.load_book_config(str(book))


def test_load_book_config_wrong_type_raises_config_error(tmp_path):
    # `sections` must be a list; a scalar is rejected with the field in the message.
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\nsections: Savory\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="sections: .*not of type 'array'"):
        config.load_book_config(str(book))


def test_load_book_config_missing_title_raises_config_error(tmp_path):
    # A well-formed mapping that omits the one required field.
    book = tmp_path / "book.yaml"
    book.write_text("subtitle: no title here\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="'title' is a required property"):
        config.load_book_config(str(book))


def test_load_book_config_accepts_a_full_valid_book(tmp_path):
    # Every documented key together validates cleanly (guards against an
    # over-strict schema rejecting real books like the shipped example).
    book = tmp_path / "book.yaml"
    book.write_text(
        "title: Demo\n"
        "subtitle: A sample\n"
        'volume: "1.0"\n'
        "language: en\n"
        "producer: me\n"
        "rights: © 2026\n"
        "content_license: CC-BY-SA-4.0\n"
        "repo_url: https://example.com\n"
        "theme: default\n"
        "recipes_dir: recipes\n"
        "illustrations_dir: assets/illustrations/recipes\n"
        "introduction: content/introduction.md\n"
        "sections: [Savory, Desserts, Beverages]\n"
        "order: []\n"
        'palette: {navy: "#16203a"}\n'
        "fonts: {display: Playfair Display}\n"
        "labels: {ingredients: Ingredientes, section_names: {Savory: Salgados}}\n",
        encoding="utf-8",
    )
    cfg = config.load_book_config(str(book))
    assert cfg.data["title"] == "Demo"


def test_load_book_config_unknown_label_key_raises_config_error(tmp_path):
    # The strictness extends into the labels block (typo'd sub-key is caught).
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\nlabels:\n  ingrediants: X\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="labels: .*ingrediants"):
        config.load_book_config(str(book))
