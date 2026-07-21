"""Unit tests for the dependency-free markdown/recipe parsing in ladle.build_html."""

from __future__ import annotations

from pathlib import Path

import pytest
from jinja2.exceptions import SecurityError

from ladle import build_html as bh
from ladle import config


# ---- inline markdown -------------------------------------------------------
def test_inline_bold_italic_and_link():
    out = str(bh.inline("**bold** and *em* see [site](https://example.com)"))
    assert "<strong>bold</strong>" in out
    assert "<em>em</em>" in out
    assert '<a href="https://example.com">site</a>' in out


def test_inline_underscore_emphasis():
    assert str(bh.inline("_soft_")) == "<em>soft</em>"


def test_inline_escapes_html():
    # Raw HTML/entities are escaped before the markdown substitutions run.
    assert "&lt;script&gt;" in str(bh.inline("<script>"))
    assert "&amp;" in str(bh.inline("salt & pepper"))


def test_inline_only_links_http_schemes():
    # A non-http target is left untouched (no anchor injected).
    assert "<a" not in str(bh.inline("[x](javascript:alert(1))"))


def test_plain_text_strips_markdown_and_links():
    assert bh.plain_text("**Chef** [Ada](https://a.b)") == "Chef Ada"


def test_plain_text_handles_none():
    assert bh.plain_text(None) == ""


# ---- paragraphs ------------------------------------------------------------
def test_paragraphs_splits_on_blank_lines():
    out = bh.paragraphs("First para.\n\nSecond para.")
    assert [str(p) for p in out] == ["First para.", "Second para."]


def test_paragraphs_bullet_list_becomes_one_para_per_item():
    out = [str(p) for p in bh.paragraphs("- one\n- two")]
    assert out == ["one", "two"]


def test_paragraphs_joins_wrapped_lines():
    out = bh.paragraphs("a line\nwrapped here")
    assert [str(p) for p in out] == ["a line wrapped here"]


def test_paragraphs_empty_input():
    assert bh.paragraphs("") == []
    assert bh.paragraphs(None) == []


# ---- front matter / sections ----------------------------------------------
def test_split_front_matter_parses_yaml_and_body():
    fm, body = bh.split_front_matter("---\ntitle: Cake\n---\n\n## STEPS\n\ndo it\n")
    assert fm == {"title": "Cake"}
    assert body.startswith("## STEPS")


def test_split_front_matter_no_front_matter():
    fm, body = bh.split_front_matter("just a body")
    assert fm == {}
    assert body == "just a body"


def numbered(*lines: str) -> list[bh.Line]:
    """Body lines as the parsers take them: (line number, text), 1-based."""
    return list(enumerate(lines, start=1))


def test_sections_of_uppercases_headings():
    body = "## Ingredients\n- salt\n## Directions\n1. mix\n"
    sec = bh.sections_of(body)
    assert set(sec) == {"INGREDIENTS", "DIRECTIONS"}
    assert sec["INGREDIENTS"] == [(2, "- salt")]


def test_sections_of_numbers_lines_from_start_offset():
    # `start` carries the file offset lost when the front matter is stripped.
    sec = bh.sections_of("## NOTES\nkeep\n", start=10)
    assert sec["NOTES"] == [(11, "keep")]


def test_sections_of_merges_a_repeated_heading():
    # Previously the second `## NOTES` reset the list and silently dropped the first.
    sec = bh.sections_of("## NOTES\nfirst\n## NOTES\nsecond\n")
    assert [text for _, text in sec["NOTES"]] == ["first", "second"]


def test_parse_ingredients_groups_by_subheading():
    lines = numbered("### For the base", "- flour", "- butter", "### Topping", "- sugar")
    groups, unclaimed = bh.parse_ingredients(lines)
    assert [g["label"] for g in groups] == ["For the base", "Topping"]
    assert [str(x) for x in groups[0]["lines"]] == ["flour", "butter"]
    assert unclaimed == []


def test_parse_ingredients_ungrouped():
    groups, _ = bh.parse_ingredients(numbered("- salt", "- pepper"))
    assert len(groups) == 1
    assert groups[0]["label"] == ""
    assert [str(x) for x in groups[0]["lines"]] == ["salt", "pepper"]


def test_parse_ingredients_returns_unclaimed_lines():
    # A numbered ingredient list and a dash with no space: both seen in the field.
    _, unclaimed = bh.parse_ingredients(numbered("- salt", "1. 2 bifes", "-(para 10 pessoas)", ""))
    assert unclaimed == [(2, "1. 2 bifes"), (3, "-(para 10 pessoas)")]


def test_parse_directions_extracts_numbered_steps():
    lines = numbered("1. Preheat the oven", "2. **Whisk** the eggs", "not a step")
    steps, unclaimed = bh.parse_directions(lines)
    assert [str(s) for s in steps] == ["Preheat the oven", "<strong>Whisk</strong> the eggs"]
    assert unclaimed == [(3, "not a step")]


def test_parse_directions_ignores_blank_lines():
    _, unclaimed = bh.parse_directions(numbered("1. mix", "", "   "))
    assert unclaimed == []


# ---- unparsed body content -------------------------------------------------
def write_recipe(tmp_path, body: str, name: str = "r.md"):
    p = tmp_path / name
    p.write_text(f"---\ntitle: X\ncategory: Savory\n---\n\n{body}", encoding="utf-8")
    return p


def test_split_front_matter_rejects_unclosed_front_matter():
    # Used to escape as a raw ValueError; now a named, friendly ConfigError.
    with pytest.raises(config.ConfigError) as e:
        bh.split_front_matter("---\ntitle: X\n\n## DIRECTIONS\n", where="r.md")
    assert "r.md" in str(e.value)
    assert "never closed" in str(e.value)


def test_body_start_line_survives_unclosed_front_matter():
    # Must not raise: it is called alongside the error path above.
    assert bh.body_start_line("---\ntitle: X\n") == 1


def test_body_start_line_after_front_matter(tmp_path):
    raw = "---\ntitle: X\n---\n\n## INGREDIENTS\n"
    # Line 5 is `## INGREDIENTS`; lines 1-3 are front matter, 4 is blank.
    assert bh.body_start_line(raw) == 5


def test_body_start_line_without_front_matter():
    assert bh.body_start_line("## INGREDIENTS\n- salt\n") == 1


def test_unparsed_content_reports_a_wrapped_step(tmp_path):
    # The dangerous case: the step renders as a complete-looking sentence with
    # the rest of the instruction gone, and a reader cannot tell.
    p = write_recipe(tmp_path, "## DIRECTIONS\n1. Beat the butter and sugar,\nthen fold in the flour.\n")
    (d,) = bh.unparsed_content(p)
    assert d.line == 8
    assert "not a numbered step" in d.message
    assert "then fold in the flour." in d.message


def test_unparsed_content_reports_an_unknown_section(tmp_path):
    # What a non-English book hits: headings are matched literally, so the whole
    # section renders as nothing.
    p = write_recipe(tmp_path, "## PREPARAÇÃO\nMexe-se tudo.\nDeixa-se repousar.\n")
    (d,) = bh.unparsed_content(p)
    assert '"## PREPARAÇÃO"' in d.message
    assert "2 lines dropped" in d.message


def test_unparsed_content_reports_text_before_the_first_heading(tmp_path):
    p = write_recipe(tmp_path, "Uma receita da avó.\n\n## NOTES\nfine\n")
    (d,) = bh.unparsed_content(p)
    assert "before the first" in d.message


def test_unparsed_content_is_quiet_on_a_clean_recipe(tmp_path):
    p = write_recipe(tmp_path, "## INGREDIENTS\n### Base\n- salt\n\n## DIRECTIONS\n1. mix\n\n## NOTES\nProse.\n")
    assert bh.unparsed_content(p) == []


def test_unparsed_content_does_not_flag_notes_prose(tmp_path):
    # NOTES renders as free prose, so nothing in it is ever dropped.
    p = write_recipe(tmp_path, "## NOTES\nAny shape at all.\n- even a bullet\n1. or a number\n")
    assert bh.unparsed_content(p) == []


def test_unparsed_content_is_sorted_by_line(tmp_path):
    p = write_recipe(tmp_path, "## DIRECTIONS\n1. mix\nstray one\n\n## INGREDIENTS\nstray two\n")
    assert [d.line for d in bh.unparsed_content(p)] == [8, 11]


@pytest.mark.parametrize(
    "recipes_dir",
    [
        config.PACKAGE_ROOT / "sample" / "recipes",
        Path(__file__).resolve().parent.parent / "examples" / "the-ladle-kitchen" / "recipes",
    ],
    ids=["sample", "example"],
)
def test_shipped_books_have_no_dropped_content(recipes_dir):
    # The bundled sample shipped a step wrapped onto a second line, so every
    # `theme preview` rendered it truncated mid-clause. Nothing we ship should
    # demonstrate the failure this check exists to catch.
    paths = sorted(recipes_dir.glob("*.md"))
    assert paths, f"no recipes found in {recipes_dir}"
    assert [str(d) for p in paths for d in bh.unparsed_content(p)] == []


def test_dropped_formats_as_file_line_message():
    # `file:line: message` is what editors and terminals make clickable.
    assert str(bh.Dropped("r.md", 12, "boom")) == "r.md:12: boom"


def test_excerpt_caps_length_and_collapses_whitespace():
    assert bh.excerpt("a   b\tc") == "a b c"
    assert len(bh.excerpt("x" * 200)) == 60


def test_warn_unparsed_content_caps_output(tmp_path, capsys):
    body = "## DIRECTIONS\n1. mix\n" + "".join(f"stray {i}\n" for i in range(12))
    write_recipe(tmp_path, body)
    bh.warn_unparsed_content(tmp_path, limit=3)
    err = capsys.readouterr().err
    assert err.count("warning:") == 4  # 3 findings + the summary line
    assert "and 9 more" in err
    assert "ladle validate" in err


# ---- titles ----------------------------------------------------------------
def test_split_title_article_pulls_leading_article():
    assert bh.split_title_article("The Best Cake") == ("The", "Best Cake")


def test_split_title_article_no_article():
    assert bh.split_title_article("Carrot Cake") == ("", "Carrot Cake")


# ---- ordering --------------------------------------------------------------
def _r(slug, category, title):
    return {"slug": slug, "category": category, "title": title}


def test_order_recipes_sorts_by_section_then_explicit_order():
    book = {"sections": ["Savory", "Desserts"], "order": ["cake", "pie"]}
    recipes = [
        _r("pie", "Desserts", "Pie"),
        _r("stew", "Savory", "Stew"),
        _r("cake", "Desserts", "Cake"),
    ]
    assert [r["slug"] for r in bh.order_recipes(recipes, book)] == ["stew", "cake", "pie"]


def test_order_recipes_unlisted_section_sorts_last_then_by_title():
    book = {"sections": ["Savory"], "order": []}
    recipes = [_r("z", "Other", "Zucchini"), _r("a", "Other", "Apple"), _r("s", "Savory", "Stew")]
    assert [r["slug"] for r in bh.order_recipes(recipes, book)] == ["s", "a", "z"]


# ---- labels ----------------------------------------------------------------
def test_merged_labels_defaults_unchanged_without_labels_block():
    labels = bh.merged_labels({})
    assert labels["ingredients"] == "Ingredients"
    assert labels["section_names"]["Savory"] == "Savory"


def test_merged_labels_overrides_top_level_and_section_names():
    labels = bh.merged_labels({"labels": {"ingredients": "Ingrédients", "section_names": {"Savory": "Salé"}}})
    assert labels["ingredients"] == "Ingrédients"
    assert labels["section_names"]["Savory"] == "Salé"
    # untouched section names keep their default
    assert labels["section_names"]["Desserts"] == "Desserts"


def test_merged_labels_does_not_mutate_module_defaults():
    bh.merged_labels({"labels": {"section_names": {"Savory": "X"}}})
    assert bh.DEFAULT_LABELS["section_names"]["Savory"] == "Savory"


# ---- schema warnings at build time (#4) ------------------------------------
def test_warn_schema_issues_warns_on_bad_recipe(tmp_path, capsys):
    (tmp_path / "bad.md").write_text("---\ntitle: X\ncategory: Nonsense\n---\n", encoding="utf-8")
    bh.warn_schema_issues(tmp_path)
    err = capsys.readouterr().err
    assert "warning:" in err
    assert "bad.md" in err


def test_warn_schema_issues_silent_on_clean_recipe(tmp_path, capsys):
    (tmp_path / "ok.md").write_text("---\ntitle: X\ncategory: Desserts\n---\n", encoding="utf-8")
    bh.warn_schema_issues(tmp_path)
    assert capsys.readouterr().err == ""


def test_warn_schema_issues_silent_on_empty_dir(tmp_path, capsys):
    # 0-recipe books are valid — no synthetic "no recipes found" warning on build.
    bh.warn_schema_issues(tmp_path)
    assert capsys.readouterr().err == ""


# ---- theme template sandbox (untrusted themes are data, not code) ----------
def test_make_env_blocks_private_attribute_access():
    # A theme reaching for dunder internals is a sandbox escape attempt.
    env = bh.make_env(Path("."))
    with pytest.raises(SecurityError):
        env.from_string("{{ ().__class__.__bases__ }}").render()


def test_make_env_allows_ordinary_theme_expressions():
    # The idioms the bundled templates rely on (dict.get, |length, |upper).
    env = bh.make_env(Path("."))
    out = env.from_string("{{ d.get('k', 'x')|upper }}-{{ items|length }}").render(d={"k": "hi"}, items=[1, 2, 3])
    assert out == "HI-3"


def test_render_template_converts_security_error_to_config_error(tmp_path):
    # A blocked template surfaces as a friendly ConfigError, not a raw traceback.
    (tmp_path / "evil.html.j2").write_text("{{ ().__class__.__bases__ }}", encoding="utf-8")
    env = bh.make_env(tmp_path)
    with pytest.raises(config.ConfigError) as excinfo:
        bh.render_template(env, "evil.html.j2")
    assert "evil.html.j2" in str(excinfo.value)
    assert "sandbox" in str(excinfo.value)
