"""Unit tests for path resolution and theme/colour helpers in ladle.config."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ladle import config
from ladle.config import BookConfig


def test_load_theme_missing_manifest_returns_defaults(tmp_path):
    # A theme dir without a theme.yaml still yields the normalized shape, and the
    # defaults are what the core hardcoded before the manifest could declare them,
    # so such a theme renders exactly as it did.
    theme = config.load_theme(tmp_path)
    assert theme.name == ""
    assert theme.palette == {} and theme.fonts == {} and theme.font_faces == []
    assert theme.params == {} and theme.labels == {}
    assert theme.trim == ["6.75in", "9.5in"]
    assert theme.template("print") == "print.html.j2"
    assert theme.template("epub") == "epub.html.j2"
    assert [p.name for p in theme.stylesheets("print")] == ["common.css", "print.css"]
    assert [p.name for p in theme.stylesheets("epub")] == ["epub.css"]


def test_load_theme_merges_manifest_over_defaults(tmp_path):
    (tmp_path / "theme.yaml").write_text("name: midnight\npalette:\n  navy: '#000'\n", encoding="utf-8")
    theme = config.load_theme(tmp_path)
    assert theme.name == "midnight"
    assert theme.palette == {"navy": "#000"}
    # keys absent from the manifest still fall back to the defaults
    assert theme.font_faces == []


def test_load_theme_partial_nested_namespace_keeps_its_siblings(tmp_path):
    # The bug a shallow `{**defaults, **data}` merge would reintroduce: declaring
    # one template used to drop the others, so the build died on a template
    # nobody named. Every nested namespace fills per key.
    (tmp_path / "theme.yaml").write_text("name: midnight\ntemplates: {print: fancy.html.j2}\n", encoding="utf-8")
    theme = config.load_theme(tmp_path)
    assert theme.template("print") == "fancy.html.j2"
    assert theme.template("epub") == "epub.html.j2"
    assert theme.template("landing") == "landing.html.j2"


def test_load_theme_partial_stylesheets_keeps_the_other_target(tmp_path):
    (tmp_path / "theme.yaml").write_text("name: midnight\nstylesheets: {print: [css/only.css]}\n", encoding="utf-8")
    theme = config.load_theme(tmp_path)
    assert [p.name for p in theme.stylesheets("print")] == ["only.css"]
    assert [p.name for p in theme.stylesheets("epub")] == ["epub.css"]


def test_load_theme_empty_stylesheet_list_is_honoured(tmp_path):
    # A theme that inlines all its CSS declares none — an empty list has to mean
    # "none", not "fall back to the defaults".
    (tmp_path / "theme.yaml").write_text("name: midnight\nstylesheets: {print: []}\n", encoding="utf-8")
    assert config.load_theme(tmp_path).stylesheets("print") == []


def test_theme_declared_tells_a_declaration_from_a_default(tmp_path):
    # What lets the build stay quiet about a theme that ships no landing page while
    # still reporting one that names a landing template it does not have.
    (tmp_path / "theme.yaml").write_text("name: midnight\ntemplates: {print: p.j2}\n", encoding="utf-8")
    theme = config.load_theme(tmp_path)
    assert theme.declared("templates.print")
    assert not theme.declared("templates.landing")
    assert not theme.declared("page.trim")


# ---- a theme is untrusted data: manifest paths may not leave the theme dir --


@pytest.mark.parametrize(
    "relpath",
    [
        "/etc/passwd",  # absolute
        "../../../etc/passwd",  # climbs out
        "css/../../secrets.css",  # climbs out after descending
        "~/secrets.css",  # home-relative
        "",  # empty
    ],
)
def test_theme_path_rejects_anything_outside_the_theme_dir(tmp_path, relpath):
    theme = config.load_theme(tmp_path)
    with pytest.raises(config.ConfigError, match="stylesheets.print"):
        theme.path(relpath, key="stylesheets.print")


def test_theme_path_rejects_a_symlink_pointing_out_of_the_theme(tmp_path):
    # The check resolves, so a path that is innocent on its face but symlinked
    # elsewhere is caught too.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secrets.css").write_text("x", encoding="utf-8")
    theme_dir = tmp_path / "theme"
    (theme_dir / "css").mkdir(parents=True)
    (theme_dir / "css" / "leak.css").symlink_to(outside / "secrets.css")
    theme = config.load_theme(theme_dir)
    with pytest.raises(config.ConfigError, match="resolves outside"):
        theme.path("css/leak.css", key="stylesheets.print")


def test_theme_path_accepts_an_ordinary_relative_path(tmp_path):
    theme = config.load_theme(tmp_path)
    assert theme.path("css/print.css") == tmp_path / "css" / "print.css"


@pytest.mark.parametrize("bad", ["/etc/passwd", "../../secrets.css", "css/../../secrets.css"])
def test_load_theme_refuses_an_escaping_path_at_load(tmp_path, bad):
    # At load, not when some caller happens to reach that file: the EPUB
    # stylesheets are read after the print HTML is already written, which is a
    # confusing place to learn the manifest was never usable. The message names the
    # manifest key rather than reporting a raw schema regex.
    (tmp_path / "theme.yaml").write_text(f"name: mini\nstylesheets: {{epub: [{bad!r}]}}\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="stylesheets.epub"):
        config.load_theme(tmp_path)


def test_load_theme_refuses_an_escaping_template_path_at_load(tmp_path):
    (tmp_path / "theme.yaml").write_text("name: mini\ntemplates: {print: '../../evil.j2'}\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="templates.print"):
        config.load_theme(tmp_path)


def test_an_escaping_path_error_is_readable(tmp_path):
    # The rule lives in the loader rather than in a schema `pattern` precisely so
    # the message can say this instead of dumping the regex at the author.
    (tmp_path / "theme.yaml").write_text(
        "name: mini\nstylesheets: {print: ['../../../etc/passwd']}\n", encoding="utf-8"
    )
    with pytest.raises(config.ConfigError) as excinfo:
        config.load_theme(tmp_path)
    message = str(excinfo.value)
    assert "leaves the theme directory" in message
    assert "^" not in message and "match" not in message


# ---- theme.yaml schema validation ------------------------------------------


def test_load_theme_unknown_key_raises_config_error(tmp_path):
    # A typo'd key (`pallete` for `palette`) is caught, not silently dropped.
    (tmp_path / "theme.yaml").write_text("name: midnight\npallete:\n  navy: '#000'\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="pallete"):
        config.load_theme(tmp_path)


def test_load_theme_missing_name_raises_config_error(tmp_path):
    # `name` is the one required field: a manifest without it fails at load.
    (tmp_path / "theme.yaml").write_text("description: no name here\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="'name' is a required property"):
        config.load_theme(tmp_path)


def test_load_theme_malformed_font_face_raises_config_error(tmp_path):
    # A font_faces entry must carry a `file`; omitting it is rejected with the location.
    (tmp_path / "theme.yaml").write_text("name: midnight\nfont_faces:\n  - {family: Bitter}\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="font_faces/0: .*'file' is a required property"):
        config.load_theme(tmp_path)


def test_load_theme_unknown_nested_key_raises_config_error(tmp_path):
    # Strictness reaches into nested objects: a typo'd sub-key of `author` is caught.
    (tmp_path / "theme.yaml").write_text("name: midnight\nauthor: {name: A. Cook, handel: '@cook'}\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="author: .*handel"):
        config.load_theme(tmp_path)


def test_load_theme_non_mapping_manifest_raises_config_error(tmp_path):
    (tmp_path / "theme.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="must be a mapping"):
        config.load_theme(tmp_path)


def test_load_theme_accepts_a_full_valid_manifest(tmp_path):
    # Every documented key together validates cleanly (guards against an
    # over-strict schema rejecting the shipped default theme).
    (tmp_path / "theme.yaml").write_text(
        "name: trattoria\n"
        "title: Trattoria\n"
        "description: Warm rustic serif.\n"
        'version: "1.2.0"\n'
        'ladle: ">=0.3,<1.0"\n'
        "author: {name: A. Cook, handle: '@cook', url: https://example.com}\n"
        "license: CC-BY-4.0\n"
        "tags: [warm, rustic, serif]\n"
        "preview: previews/cover.png\n"
        'page: {trim: ["148mm", "210mm"]}\n'
        "stylesheets: {print: [css/pocket.css], epub: [css/pocket.css]}\n"
        "templates: {print: print.html.j2, epub: epub.html.j2}\n"
        'palette: {navy: "#16203a"}\n'
        "fonts: {display: Bitter}\n"
        "labels: {contents: Sommaire, dedication: For Ma}\n"
        "params: {column_ratio: 1.8, folio_position: footer}\n"
        "font_faces: [{family: Bitter, file: Bitter.ttf, style: normal}]\n"
        "fonts_meta: [{family: Bitter, license: OFL-1.1, source: https://example.com}]\n",
        encoding="utf-8",
    )
    theme = config.load_theme(tmp_path)
    assert theme.name == "trattoria"
    assert theme.data["tags"] == ["warm", "rustic", "serif"]
    assert theme.trim == ["148mm", "210mm"]
    assert theme.params == {"column_ratio": 1.8, "folio_position": "footer"}
    # A string ladle has never heard of is a theme's to invent.
    assert theme.labels["dedication"] == "For Ma"


def test_default_theme_manifest_validates():
    # The shipped default theme must satisfy its own schema.
    theme = config.load_theme(config.THEMES_DIR / "default")
    assert theme.name == "default"


def test_default_theme_declares_every_optional_namespace():
    # The bundled theme is the reference implementation people copy, and it has to
    # be reproducible from its manifest alone — so it declares what it uses rather
    # than leaning on a core default.
    theme = config.load_theme(config.THEMES_DIR / "default")
    for dotted in ("page.trim", "stylesheets.print", "stylesheets.epub", "templates.print", "labels", "params"):
        assert theme.declared(dotted), f"the bundled theme should declare {dotted}"


def test_default_theme_declares_only_files_that_exist():
    # Guards the reference implementation against drifting from its own manifest.
    theme = config.load_theme(config.THEMES_DIR / "default")
    for target in ("print", "epub"):
        for sheet in theme.stylesheets(target):
            assert sheet.exists(), f"stylesheets.{target} names a missing {sheet.name}"
        assert theme.template_path(target).exists(), f"templates.{target} is missing"
    for face in theme.font_faces:
        assert (theme.fonts_dir / face["file"]).exists(), f"font file {face['file']} is missing"


def test_default_theme_trim_agrees_with_its_print_css():
    # The one fact declared twice: the manifest says it and `@page { size }` paints
    # it. `validate` catches drift in the built PDF; this catches it at the source.
    theme = config.load_theme(config.THEMES_DIR / "default")
    css = (theme.dir / "css" / "print.css").read_text(encoding="utf-8")
    assert f"size: {theme.trim[0]} {theme.trim[1]};" in css


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


def test_theme_dir_dot_slash_stays_next_to_the_book(tmp_path):
    # `./mytheme` is the most natural way to point at a folder beside your book,
    # and it used to send ladle into its own installation directory: the test was
    # the reference's component count, and Path("./mytheme") has exactly one.
    (tmp_path / "mytheme").mkdir()
    cfg = config.BookConfig(path=tmp_path / "book.yaml", data={"theme": "./mytheme"})
    assert cfg.theme_dir == tmp_path / "mytheme"


def test_theme_dir_dot_slash_is_a_path_even_when_nothing_is_there(tmp_path):
    # It must not fall through to the bundled themes and report a site-packages
    # path the author never typed.
    cfg = config.BookConfig(path=tmp_path / "book.yaml", data={"theme": "./gone"})
    assert cfg.theme_dir == tmp_path / "gone"


def test_theme_dir_bare_name_prefers_a_theme_vendored_with_the_book(tmp_path):
    # The order Hugo and Zola use: <book>/themes/<name> before the installed set,
    # so a book can carry its own theme without naming paths.
    (tmp_path / "themes" / "mine").mkdir(parents=True)
    cfg = config.BookConfig(path=tmp_path / "book.yaml", data={"theme": "mine"})
    assert cfg.theme_dir == tmp_path / "themes" / "mine"


def test_a_vendored_theme_shadows_a_bundled_one_of_the_same_name(tmp_path):
    (tmp_path / "themes" / "default").mkdir(parents=True)
    cfg = config.BookConfig(path=tmp_path / "book.yaml", data={"theme": "default"})
    assert cfg.theme_dir == tmp_path / "themes" / "default"


def test_theme_dir_expands_a_home_relative_path(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = config.BookConfig(path=Path("/tmp/demo/book.yaml"), data={"theme": "~/themes/mine"})
    assert cfg.theme_dir == tmp_path / "themes" / "mine"


def test_require_theme_dir_names_every_directory_it_searched(tmp_path):
    # The failure this replaces named one path inside site-packages, which is
    # neither where the author looked nor anywhere they had written.
    cfg = config.BookConfig(path=tmp_path / "book.yaml", data={"theme": "nosuch"})
    with pytest.raises(config.ThemeNotFoundError) as e:
        cfg.require_theme_dir()
    message = str(e.value)
    assert "nosuch" in message
    assert config.rel(tmp_path / "themes" / "nosuch") in message
    assert config.rel(config.THEMES_DIR / "nosuch") in message
    assert "default" in message  # the bundled themes that do exist


def test_require_theme_dir_returns_the_directory_when_it_is_there():
    cfg = config.BookConfig(path=Path("/tmp/demo/book.yaml"), data={"theme": "default"})
    assert cfg.require_theme_dir() == config.THEMES_DIR / "default"


def test_theme_not_found_is_a_config_error(tmp_path):
    # So the top-level guard keeps mapping it to a clean exit-1 message.
    assert issubclass(config.ThemeNotFoundError, config.ConfigError)


def test_is_bundled_theme_distinguishes_shipped_from_authors_own(tmp_path):
    # Decides how strictly the build checks a theme's templates: a theme we ship
    # is fixed in the same commit that changes the contract, an author's is not.
    assert config.is_bundled_theme(config.THEMES_DIR / "default")
    assert not config.is_bundled_theme(tmp_path / "themes" / "mine")


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


def test_load_book_config_accepts_a_label_key_the_core_never_heard_of(tmp_path):
    # `labels` is deliberately open now: the keys belong to the active theme, so a
    # theme that prints a dedication page can be translated by its book. The typo
    # protection a closed enum gave moves to a build-time warning naming the key —
    # see test_build_html's undeclared-label tests.
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\nlabels:\n  dedication: For Ma\n", encoding="utf-8")
    assert config.load_book_config(str(book)).data["labels"] == {"dedication": "For Ma"}


def test_load_book_config_rejects_a_label_that_is_not_a_string(tmp_path):
    # Open on keys, not on shape: a label is a string, or the nested section_names
    # mapping. A list is a mistake worth catching at load.
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\nlabels:\n  contents: [a, b]\n", encoding="utf-8")
    with pytest.raises(config.ConfigError, match="labels/contents"):
        config.load_book_config(str(book))


def test_load_book_config_accepts_free_form_params(tmp_path):
    # The theme owns the vocabulary, so the core cannot type-check these keys; an
    # undeclared one is warned about at build time instead.
    book = tmp_path / "book.yaml"
    book.write_text("title: Demo\nparams:\n  column_ratio: 2.4\n  section_openers: true\n", encoding="utf-8")
    assert config.load_book_config(str(book)).data["params"]["column_ratio"] == 2.4


# ---- the precedence contract is one table, not two ---------------------------
def test_the_theming_docs_precedence_table_matches_the_code():
    # The claim in docs/THEMING.md is that its table and the two namespace tuples
    # are the same contract. When it lived only in prose, the merge and the docs
    # drifted and a documented palette override stopped reaching the PDF.
    doc_path = config.PACKAGE_ROOT.parent.parent / "docs" / "THEMING.md"
    if not doc_path.exists():
        pytest.skip("docs/ is not shipped in the installed package")
    rows = re.findall(r"^\| `([a-z_]+)(?:\.\*)?` \| (yes) \| (\*\*no\*\*|per key) \|", doc_path.read_text(), re.M)
    assert rows, "the precedence table in docs/THEMING.md was not found"
    overridable = tuple(name for name, _, book in rows if book == "per key")
    theme_owned = tuple(name for name, _, book in rows if book == "**no**")
    assert overridable == config.OVERRIDABLE_NAMESPACES
    assert theme_owned == config.THEME_OWNED_NAMESPACES


def test_every_namespace_in_the_contract_is_a_real_manifest_key():
    # Neither tuple may name a namespace the manifest does not normalize, or the
    # merge would read an attribute that is not there.
    theme = config.load_theme(config.THEMES_DIR / "default")
    for ns in (*config.OVERRIDABLE_NAMESPACES, *config.THEME_OWNED_NAMESPACES):
        assert ns in theme.data, f"{ns} is in the precedence contract but not in the manifest"


def test_the_two_namespace_groups_do_not_overlap():
    assert set(config.OVERRIDABLE_NAMESPACES) & set(config.THEME_OWNED_NAMESPACES) == set()
