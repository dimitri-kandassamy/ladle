"""Unit tests for the dependency-free markdown/recipe parsing in ladle.build_html."""

from __future__ import annotations

from ladle import build_html as bh


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


def test_sections_of_uppercases_headings():
    body = "## Ingredients\n- salt\n## Directions\n1. mix\n"
    sec = bh.sections_of(body)
    assert set(sec) == {"INGREDIENTS", "DIRECTIONS"}
    assert sec["INGREDIENTS"] == ["- salt"]


def test_parse_ingredients_groups_by_subheading():
    lines = ["### For the base", "- flour", "- butter", "### Topping", "- sugar"]
    groups = bh.parse_ingredients(lines)
    assert [g["label"] for g in groups] == ["For the base", "Topping"]
    assert [str(x) for x in groups[0]["lines"]] == ["flour", "butter"]


def test_parse_ingredients_ungrouped():
    groups = bh.parse_ingredients(["- salt", "- pepper"])
    assert len(groups) == 1
    assert groups[0]["label"] == ""
    assert [str(x) for x in groups[0]["lines"]] == ["salt", "pepper"]


def test_parse_directions_extracts_numbered_steps():
    lines = ["1. Preheat the oven", "2. **Whisk** the eggs", "not a step"]
    steps = [str(s) for s in bh.parse_directions(lines)]
    assert steps == ["Preheat the oven", "<strong>Whisk</strong> the eggs"]


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
