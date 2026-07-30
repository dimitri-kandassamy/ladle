"""Unit tests for the dependency-free markdown/recipe parsing in ladle.build_html."""

from __future__ import annotations

import re
import shutil
import zlib
from pathlib import Path

import pytest
import yaml
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


def test_inline_internal_cross_reference_to_a_slug():
    # `[Label](#slug)` becomes an in-book cross-reference tagged for the theme to
    # resolve the target's page number; it is not a plain external link.
    out = str(bh.inline("see [Carrot Cake](#carrot-cake)"))
    assert '<a class="xref" href="#carrot-cake">Carrot Cake</a>' in out


def test_inline_cross_reference_slug_must_be_anchor_shaped():
    # A `#` target that isn't a bare slug (spaces, uppercase) is left as text.
    assert "<a" not in str(bh.inline("[x](#Not A Slug)"))


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


# ---- markdown section bodies -----------------------------------------------
def test_render_markdown_joins_a_wrapped_step():
    """The field report's worst case: 25 files, steps truncated mid-sentence."""
    html = bh.render_markdown("1. Beat the butter,\nthen fold in the flour.")
    assert str(html) == "<ol><li>Beat the butter, then fold in the flour.</li></ol>"


def test_render_markdown_emits_ordered_and_unordered_lists():
    assert str(bh.render_markdown("1. First\n2. Second")) == "<ol><li>First</li><li>Second</li></ol>"
    assert str(bh.render_markdown("- salt\n- pepper")) == "<ul><li>salt</li><li>pepper</li></ul>"


def test_render_markdown_subheading_starts_a_new_block_without_a_blank_line():
    html = bh.render_markdown("### Sauce\n- butter\n- flour")
    assert str(html) == "<h3>Sauce</h3>\n<ul><li>butter</li><li>flour</li></ul>"


def test_render_markdown_switching_marker_starts_a_new_list():
    html = bh.render_markdown("- salt\n1. First")
    assert str(html) == "<ul><li>salt</li></ul>\n<ol><li>First</li></ol>"


def test_render_markdown_keeps_prose_the_parsers_used_to_drop():
    """Each shape below was silently discarded by the old line grammar."""
    assert "<p>For the base:</p>" in str(bh.render_markdown("For the base:\n\n- flour"))
    assert str(bh.render_markdown("-(para 10 pessoas)")) == "<p>-(para 10 pessoas)</p>"
    assert str(bh.render_markdown("NOTA: use cold butter.")) == "<p>NOTA: use cold butter.</p>"


def test_render_markdown_inline_spans_a_wrapped_line():
    html = bh.render_markdown("1. Use **very cold\nbutter** here.")
    assert str(html) == "<ol><li>Use <strong>very cold butter</strong> here.</li></ol>"


def test_render_markdown_escapes_html():
    assert "&lt;script&gt;" in str(bh.render_markdown("- <script>alert(1)</script>"))


def test_render_markdown_empty_input():
    assert str(bh.render_markdown("")) == ""
    assert str(bh.render_markdown(None)) == ""


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


def test_unparsed_content_is_silent_on_a_wrapped_step(tmp_path):
    """The report's worst case is now rendered, not reported — nothing is lost."""
    p = write_recipe(tmp_path, "## DIRECTIONS\n1. Beat the butter and sugar,\nthen fold in the flour.\n")
    assert bh.unparsed_content(p) == []


def test_unparsed_content_is_silent_on_shapes_the_old_grammar_rejected(tmp_path):
    """Numbered ingredients, an unbulleted line, a prose lead-in: all render now."""
    p = write_recipe(
        tmp_path,
        "## INGREDIENTS\nFor the base:\n\n1. 2 bifes\n-(para 10 pessoas)\n\n## DIRECTIONS\n1. mix\n",
    )
    assert bh.unparsed_content(p) == []


def test_unparsed_content_reports_an_unknown_section(tmp_path):
    # A book written to another project's conventions. The content still renders,
    # as a generic titled block — the warning is so the author can rename it.
    p = write_recipe(tmp_path, "## PREPARAÇÃO\nMexe-se tudo.\nDeixa-se repousar.\n")
    (d,) = bh.unparsed_content(p)
    assert '"## PREPARAÇÃO"' in d.message
    assert "generic block" in d.message


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
    p = write_recipe(tmp_path, "Uma receita da avó.\n\n## DIRECTIONS\n1. mix\n\n## PREPARAÇÃO\nMexe-se tudo.\n")
    assert [d.line for d in bh.unparsed_content(p)] == [6, 12]


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


# ---- cross-references ------------------------------------------------------
def test_unresolved_xrefs_accepts_a_reference_to_a_sibling_recipe(tmp_path):
    write_recipe(tmp_path, "## NOTES\nServe with [Greens](#greens).\n", name="cake.md")
    write_recipe(tmp_path, "## NOTES\nfine\n", name="greens.md")
    assert bh.unresolved_xrefs(sorted(tmp_path.glob("*.md"))) == []


def test_unresolved_xrefs_reports_a_slug_no_recipe_has(tmp_path):
    write_recipe(tmp_path, "## NOTES\nSee [Missing](#no-such-recipe).\n", name="cake.md")
    (d,) = bh.unresolved_xrefs(sorted(tmp_path.glob("*.md")))
    assert d.file == "cake.md"
    assert d.line == 7  # 4 lines of front matter, a blank, then `## NOTES`
    assert "#no-such-recipe" in d.message


def test_unresolved_xrefs_honours_an_explicit_slug(tmp_path):
    # The target's slug comes from front matter when set, not from the filename.
    (tmp_path / "01-greens.md").write_text(
        "---\ntitle: X\ncategory: Savory\nslug: skillet-greens\n---\n\n## NOTES\nfine\n", encoding="utf-8"
    )
    write_recipe(tmp_path, "## NOTES\n[G](#skillet-greens) and [F](#01-greens).\n", name="cake.md")
    (d,) = bh.unresolved_xrefs(sorted(tmp_path.glob("*.md")))
    assert "#01-greens" in d.message


def test_unresolved_xrefs_reports_a_draft_target_distinctly(tmp_path):
    # A draft is filtered out of both builds, so its anchor never exists — but the
    # slug is right there in the folder, so say why rather than "no such recipe".
    (tmp_path / "greens.md").write_text(
        "---\ntitle: X\ncategory: Savory\ndraft: true\n---\n\n## NOTES\nfine\n", encoding="utf-8"
    )
    write_recipe(tmp_path, "## NOTES\nSee [Greens](#greens).\n", name="cake.md")
    (d,) = bh.unresolved_xrefs(sorted(tmp_path.glob("*.md")))
    assert "draft" in d.message


def test_unresolved_xrefs_scans_the_front_matter_story(tmp_path):
    # `story:` renders through the same inline markdown as the body, so a dead
    # reference there breaks the same way.
    (tmp_path / "cake.md").write_text(
        "---\ntitle: X\ncategory: Savory\nstory: 'After the [Greens](#greens).'\n---\n\n## NOTES\nfine\n",
        encoding="utf-8",
    )
    (d,) = bh.unresolved_xrefs(sorted(tmp_path.glob("*.md")))
    assert d.line == 4


def test_unresolved_xrefs_ignores_external_links(tmp_path):
    write_recipe(tmp_path, "## NOTES\n[site](https://example.com/#anchor)\n", name="cake.md")
    assert bh.unresolved_xrefs(sorted(tmp_path.glob("*.md"))) == []


@pytest.mark.parametrize(
    "recipes_dir",
    [
        config.PACKAGE_ROOT / "sample" / "recipes",
        Path(__file__).resolve().parent.parent / "examples" / "the-ladle-kitchen" / "recipes",
    ],
    ids=["sample", "example"],
)
def test_shipped_books_have_no_dead_cross_references(recipes_dir):
    # A dead reference in a shipped book would fail `ladle validate` downstream
    # with an epubcheck error (RSC-012) naming a generated file.
    assert [str(d) for d in bh.unresolved_xrefs(sorted(recipes_dir.glob("*.md")))] == []


def test_warn_unresolved_xrefs_caps_output(tmp_path, capsys):
    for i in range(12):
        write_recipe(tmp_path, f"## NOTES\n[x](#gone-{i})\n", name=f"r{i}.md")
    bh.warn_unresolved_xrefs(tmp_path, limit=3)
    err = capsys.readouterr().err
    assert err.count("warning:") == 4  # 3 findings + the summary line
    assert "and 9 more" in err


def test_dropped_formats_as_file_line_message():
    # `file:line: message` is what editors and terminals make clickable.
    assert str(bh.Dropped("r.md", 12, "boom")) == "r.md:12: boom"


def test_excerpt_caps_length_and_collapses_whitespace():
    assert bh.excerpt("a   b\tc") == "a b c"
    assert len(bh.excerpt("x" * 200)) == 60


def test_warn_unparsed_content_caps_output(tmp_path, capsys):
    for i in range(12):
        write_recipe(tmp_path, f"## SECTION {i}\ncontent\n", name=f"r{i}.md")
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


# ---- the derived table of contents -----------------------------------------
def _toc(recipes, **book):
    book.setdefault("labels", bh.merged_labels({}))
    return bh.build_toc(recipes, book)


def test_build_toc_groups_by_declared_sections_in_declared_order():
    recipes = [_r("stew", "Savory", "Stew"), _r("cake", "Desserts", "Cake")]
    toc = _toc(recipes, sections=["Desserts", "Savory"])
    assert [(s["title"], [r["slug"] for r in s["recipes"]]) for s in toc] == [
        ("Desserts", ["cake"]),
        ("Savory", ["stew"]),
    ]


def test_build_toc_derives_sections_when_the_book_declares_none():
    # The A3 regression: `sections:` is optional, and a book without it used to
    # get a Contents page with a heading, a rule, and no entries.
    recipes = [_r("stew", "Savory", "Stew"), _r("cake", "Desserts", "Cake")]
    toc = _toc(recipes)
    assert [s["name"] for s in toc] == ["Savory", "Desserts"]  # the recipes' own order
    assert [r["slug"] for s in toc for r in s["recipes"]] == ["stew", "cake"]


def test_build_toc_keeps_a_recipe_whose_category_no_section_declares():
    # Undeclared categories follow the declared ones, so every printed recipe has
    # a contents entry rather than being silently left out of the front matter.
    recipes = [_r("stew", "Savory", "Stew"), _r("gin", "Beverages", "Gin")]
    assert [s["name"] for s in _toc(recipes, sections=["Savory"])] == ["Savory", "Beverages"]


def test_build_toc_drops_a_declared_section_with_no_recipes():
    assert [s["name"] for s in _toc([_r("stew", "Savory", "S")], sections=["Savory", "Desserts"])] == ["Savory"]


def test_build_toc_is_empty_for_a_book_with_no_recipes():
    assert _toc([], sections=["Savory"]) == []


def test_build_toc_titles_come_from_the_books_section_labels():
    book = {"labels": bh.merged_labels({"labels": {"section_names": {"Savory": "Salé"}}})}
    assert bh.build_toc([_r("stew", "Savory", "Stew")], book)[0]["title"] == "Salé"


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


# ---- the bundled theme's page structure ------------------------------------
def a_recipe(**over) -> dict:
    """One synthetic recipe in the shape `load_recipe` produces."""
    r = {
        "slug": "cake",
        "title": "Cake",
        "category": "Desserts",
        "servings": "",
        "credits": "",
        "credits_line": "",
        "attribution": "",
        "has_story": False,
        "story_html": [],
        "author": {"name": "", "org": ""},
        "headshot_url": "",
        "illustration_url": "",
        "ingredients_html": bh.Markup("<ul><li>flour</li></ul>"),
        "directions_html": bh.Markup("<ol><li>Mix.</li></ol>"),
        "notes_html": bh.Markup(""),
        "extra_sections": [],
        "draft": False,
    }
    r.update(over)
    return r


def render_print(*, recipes=None, book=None, font_face_css="", css_links=(), **recipe) -> str:
    """Render the bundled print template. Bare kwargs override the one recipe."""
    b = {
        "title": "The Book",
        "title_article": "The",
        "title_rest": "Book",
        "subtitle": "",
        "volume": "",
        "producer": "",
        "rights": "",
        "language": "en",
        "sections": ["Savory", "Desserts"],
        "section_openers": False,
        "palette": dict.fromkeys(("navy", "cream", "ink", "ink_deep", "rule"), "#000"),
        "fonts": {"display": "D", "body": "B"},
        "labels": bh.merged_labels({}),
    }
    b.update(book or {})
    rs = recipes if recipes is not None else [a_recipe(**recipe)]
    theme = config.PACKAGE_ROOT / "themes" / "default"
    # strict=True, as `render` uses for a bundled theme: a template that reads
    # something outside the context it is passed should fail these tests loudly.
    env = bh.make_env(theme / "templates", strict=True)
    return bh.render_template(
        env,
        "print.html.j2",
        book=b,
        intro={"title": "Intro", "from_name": "", "from_org": "", "body_html": []},
        recipes=rs,
        toc=bh.build_toc(rs, b),
        font_face_css=font_face_css,
        css_links=list(css_links),
    )


def test_font_face_css_survives_the_autoescaping_template():
    # The regression this guards: font_face_css used to return a plain str, so the
    # autoescaping environment turned url("…") into url(&#34;…&#34;). Entities are
    # not decoded inside a <style> element, so every @font-face was invalid and the
    # book silently set in a system fallback font.
    theme = config.PACKAGE_ROOT / "themes" / "default"
    css = bh.font_face_css(theme / "fonts", config.load_theme(theme)["font_faces"])
    html = render_print(font_face_css=css)
    style = html.split("</style>", 1)[0]
    assert "&#34;" not in style and "&amp;" not in style
    assert 'format("truetype")' in style
    assert 'font-family:"Playfair Display"' in style


def test_font_face_css_escapes_a_family_that_would_break_out_of_the_style_block():
    # A theme is untrusted data and font_face_css is marked safe, so it escapes its
    # own input: a family name may not close the CSS string or the <style> element.
    css = str(bh.font_face_css(Path("/f"), [{"family": "</style><script>x", "file": "a.ttf"}]))
    assert "</style>" not in css
    assert "<script>" not in css


def embedded_font_subsets(pdf: bytes) -> set[str]:
    """Embedded font subset names (``ABCDEF+Family``) in *pdf*.

    Reads the PDF directly rather than shelling out to poppler's `pdffonts`: the
    test job installs WeasyPrint's native libraries but not poppler, so a check
    that needed it would silently skip in CI — which is the failure mode this
    whole test exists to prevent.
    """
    names = set(re.findall(rb"/([A-Z]{6}\+[A-Za-z0-9\-]+)", pdf))
    for stream in re.findall(rb"stream\r?\n(.*?)endstream", pdf, re.S):
        try:
            names.update(re.findall(rb"/([A-Z]{6}\+[A-Za-z0-9\-]+)", zlib.decompress(stream)))
        except zlib.error:
            continue  # not a flate stream (an embedded image, a font file)
    return {n.decode() for n in names}


def test_the_themes_declared_fonts_reach_the_pdf(tmp_path, monkeypatch):
    # The guarantee the unit tests above only approximate, and the one nothing
    # checked before: the built book sets in the theme's own type. When the
    # @font-face rules are malformed WeasyPrint falls back to a system serif
    # without a word — so the PDF still renders, still paginates, still has the
    # right trim and page count, and passes every other check in the suite.
    #
    # It goes through `render()` and the real cookbook.html rather than calling
    # font_face_css directly, because the defect this guards was in neither the
    # function nor the template but in the seam between them.
    from weasyprint import HTML

    monkeypatch.setenv("LADLE_BUILD", str(tmp_path))
    bh.render(str(config.SAMPLE_BOOK))
    pdf = HTML(filename=str(tmp_path / "cookbook.html")).write_pdf()

    embedded = embedded_font_subsets(pdf)
    faces = config.load_theme(config.PACKAGE_ROOT / "themes" / "default")["font_faces"]
    for family in sorted({f["family"] for f in faces}):
        stem = family.replace(" ", "-")
        assert any(name.split("+", 1)[1].startswith(stem) for name in embedded), (
            f"{family!r} is declared in theme.yaml but is not embedded in the PDF; got {sorted(embedded)}"
        )


def test_a_scaffolded_book_gets_a_contents_page_with_entries(tmp_path, monkeypatch):
    # A3, end to end and from the front door: `ladle new` writes a book.yaml with
    # `sections:` commented out because it is optional, and the Contents page came
    # out empty — heading, rule, nothing else — while the build exited 0. Every
    # first run produced it, and the EPUB disagreed, since pandoc builds its own
    # navigation from the headings.
    from ladle import new_book

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LADLE_BUILD", str(tmp_path / "build"))
    assert new_book.main(["demo"]) == 0
    bh.render(str(tmp_path / "demo" / "book.yaml"))

    html = (tmp_path / "build" / "cookbook.html").read_text(encoding="utf-8")
    toc = html.split('<nav class="toc">')[1].split("</nav>")[0]
    assert 'href="#example-recipe"' in toc, f"scaffolded book has an empty contents page: {toc!r}"


def first_box(page, css_class: str):
    """The first box on *page* whose element carries *css_class*."""

    def walk(box):
        yield box
        for child in getattr(box, "all_children", lambda: [])():
            yield from walk(child)

    for box in walk(page._page_box):
        element = getattr(box, "element", None)
        if element is not None and css_class in (element.get("class") or "").split():
            return box
    raise AssertionError(f"no box with class {css_class!r} on this page")


def test_a_books_token_overrides_reach_the_render(tmp_path, monkeypatch):
    # theme.yaml tokens are documented as defaults a book.yaml overrides per key.
    # The merge was right and the override was emitted, but the token <style> block
    # came *before* the <link> tags and common.css declared the same `:root` — equal
    # specificity, later rule wins — so every override was discarded and no book has
    # ever been able to restyle a theme without forking it.
    #
    # Asserting on the generated HTML cannot catch this: the override is in the
    # markup either way, and only the cascade decides which value computes. So this
    # goes through WeasyPrint and reads the computed style, as the fix's proof did.
    from weasyprint import HTML

    monkeypatch.setenv("LADLE_BUILD", str(tmp_path / "build"))
    book_dir = shutil.copytree(config.SAMPLE_BOOK.parent, tmp_path / "book")
    book_path = book_dir / "book.yaml"
    book = yaml.safe_load(book_path.read_text(encoding="utf-8"))
    book["palette"] = {"navy": "#ff0000"}
    book["fonts"] = {"display": "Courier"}
    book_path.write_text(yaml.safe_dump(book), encoding="utf-8")

    bh.render(str(book_path))
    cover = HTML(filename=str(tmp_path / "build" / "cookbook.html")).render().pages[0]

    # The cover is `background: var(--navy)` and its title `font-family: var(--display)`.
    background = first_box(cover, "cover").style["background_color"]
    assert background.to("srgb").coordinates == (1.0, 0.0, 0.0), f"cover is {background}, not the book's #ff0000"
    assert "Courier" in first_box(cover, "title").style["font_family"]


def test_the_theme_does_not_redeclare_the_injected_tokens():
    # The companion to the test above, and the cheaper half: a stylesheet that
    # declares `:root` re-asserts a theme default from a later rule. Defaults belong
    # in theme.yaml, which is the only place the merge reads them from.
    css_dir = config.PACKAGE_ROOT / "themes" / "default" / "css"
    for sheet in ("common.css", "print.css"):
        rules = re.sub(r"/\*.*?\*/", "", (css_dir / sheet).read_text(encoding="utf-8"), flags=re.S)
        assert ":root" not in rules, f"{sheet} declares :root; design tokens are theme.yaml's job"


def test_the_token_block_comes_after_every_stylesheet_link():
    # The contract the fix rests on, stated where a theme author would break it.
    head = render_print(css_links=["a.css", "b.css"]).split("</head>", 1)[0]
    assert head.rindex("<style>") > head.rindex("<link")


def test_print_recipe_without_story_or_art_is_one_page():
    # The opener page exists to carry hero art. With no art and no story it would
    # be a title on an otherwise blank sheet, so the recipe collapses to one.
    html = render_print()
    assert 'class="page cream recipe"' in html
    assert "recipe-head" not in html


def test_print_recipe_with_an_illustration_keeps_its_opener():
    html = render_print(illustration_url="art/cake.svg")
    assert 'class="page cream recipe-head opener"' in html
    assert 'class="page cream method"' in html


def test_print_recipe_with_a_story_keeps_its_story_page():
    html = render_print(has_story=True, story_html=["Once."])
    assert 'class="page cream recipe-head story"' in html
    assert 'class="page cream method"' in html


def test_print_every_recipe_layout_carries_a_folio():
    # The contents resolves page numbers with target-counter; without a printed
    # folio those numbers point at nothing on paper.
    for kwargs in ({}, {"illustration_url": "a.svg"}, {"has_story": True}):
        assert '<div class="folio"></div>' in render_print(**kwargs)


def test_print_contents_lists_the_recipes_of_a_book_that_declares_no_sections():
    # A3: the loop used to read book.sections, which most books never set, so the
    # Contents page printed a heading, a rule and nothing else.
    recipes = [a_recipe(), a_recipe(slug="stew", title="Stew", category="Savory")]
    html = render_print(recipes=recipes, book={"sections": []})
    toc = html.split('<nav class="toc">')[1].split("</nav>")[0]
    assert 'href="#cake"' in toc
    assert 'href="#stew"' in toc
    assert "Desserts" in toc and "Savory" in toc


def test_print_contents_has_no_footer():
    # It fragments across sheets, and an absolutely-positioned footer would land
    # on only one of them.
    html = render_print()
    contents = html.split('class="page cream contents"')[1].split("</section>")[0]
    assert "footer" not in contents


def test_print_method_less_recipe_gets_a_note_instead_of_an_empty_column():
    html = render_print(directions_html=bh.Markup(""))
    assert "no-method" in html
    assert bh.DEFAULT_LABELS["no_method"] in html


def test_print_has_an_interior_title_page():
    assert 'class="page cream title-page"' in render_print()


def test_print_cover_omits_an_unset_volume():
    # An unset `volume:` used to print the bare word "Volume" with nothing after.
    assert "volume" not in render_print(book={"volume": ""})
    assert "Volume 2" in render_print(book={"volume": "2"})


def test_print_no_line_art_anywhere():
    # The navy pages carry colour and paper grain only; the scattered motif is
    # gone, and with it the div that positioned it.
    assert 'class="pattern"' not in render_print()


def test_print_section_openers_are_off_by_default():
    two = [a_recipe(slug="a", category="Savory"), a_recipe(slug="b", category="Desserts")]
    assert "section-opener" not in render_print(recipes=two)


def test_print_section_openers_when_enabled():
    # One divider per section, not per recipe, and named from `section_names`.
    two_each = [
        a_recipe(slug="a", category="Savory"),
        a_recipe(slug="b", category="Savory"),
        a_recipe(slug="c", category="Desserts"),
    ]
    html = render_print(recipes=two_each, book={"section_openers": True})
    assert html.count("section-opener") == 2
    assert ">Savory</h1>" in html and ">Desserts</h1>" in html


def test_print_section_openers_use_the_books_section_names():
    # A translated book names its dividers through `labels:`, like the rest of
    # the chrome — the category key itself is never printed.
    labels = bh.merged_labels({"labels": {"section_names": {"Savory": "Salgados"}}})
    html = render_print(
        recipes=[a_recipe(category="Savory")],
        book={"section_openers": True, "labels": labels},
    )
    assert ">Salgados</h1>" in html


def test_print_outline_nests_recipes_only_when_sectioned():
    # The demotion to bookmark-level 2 keys off the same flag as the openers:
    # with no opener above it, a demoted recipe would nest under the intro.
    assert 'class="sectioned"' not in render_print()
    assert 'class="sectioned"' in render_print(book={"section_openers": True})


def test_print_author_byline_needs_a_story():
    # `author` is who tells the story; provenance without one is `credits`.
    assert "Recipe by" not in render_print(author={"name": "Ada", "org": ""})
    assert "Recipe by" in render_print(has_story=True, author={"name": "Ada", "org": ""})


def laid_out_text(html: str) -> str:
    """All text WeasyPrint actually places on a page, with the theme's real CSS.

    Markup assertions cannot see this class of bug: the ingredients are in the
    HTML either way, and only the layout decides whether they land on a sheet or
    in a fragment that `overflow: hidden` discards.
    """
    from weasyprint import HTML

    theme = config.PACKAGE_ROOT / "themes" / "default"
    links = "".join(
        f'<link rel="stylesheet" href="{(theme / "css" / name).as_uri()}">' for name in ("common.css", "print.css")
    )
    # Before the token <style>, which `render` emits last on purpose: injecting the
    # links after it would give this helper the opposite cascade to a real build.
    doc = HTML(string=html.replace("<style>", links + "<style>", 1), base_url=str(theme)).render()

    def walk(box, out):
        for child in getattr(box, "all_children", lambda: [])():
            if hasattr(child, "text") and child.text.strip():
                out.append(child.text.strip())
            walk(child, out)
        return out

    return " ".join(t for page in doc.pages for t in walk(page._page_box, []))


def test_print_an_overlong_recipe_still_shows_its_ingredients():
    """A recipe whose method overruns the sheet must not lose the other column.

    The column row is pinned to the sheet height for this reason. Unpinned, the
    row grows to the method's full height, fragments, and the ingredients column
    lands past the first sheet where `overflow: hidden` discards every line of
    it — which is what happened, unnoticed, until a 60-step recipe was tried.
    """
    steps = "".join(f"<li>Step {i}. " + "words " * 25 + "</li>" for i in range(60))
    html = render_print(
        ingredients_html=bh.Markup("<ul>" + "".join(f"<li>Ingredient {i}</li>" for i in range(40)) + "</ul>"),
        directions_html=bh.Markup(f"<ol>{steps}</ol>"),
    )
    text = laid_out_text(html)
    assert "Ingredient 0" in text
    assert "Step 0." in text


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


def test_make_env_strict_names_what_a_bundled_template_got_wrong(tmp_path):
    # What A3 cost us: looping over an undefined value renders nothing and exits 0.
    # For themes we ship, that is an error with a name on it instead.
    (tmp_path / "t.html.j2").write_text("{% for s in nope %}{{ s }}{% endfor %}", encoding="utf-8")
    env = bh.make_env(tmp_path, strict=True)
    with pytest.raises(config.ConfigError) as excinfo:
        bh.render_template(env, "t.html.j2")
    assert "t.html.j2" in str(excinfo.value)
    assert "nope" in str(excinfo.value)


def test_make_env_is_lenient_by_default_for_third_party_themes():
    # Strictness is a contract change, so it waits for the theme API version field.
    assert bh.make_env(Path(".")).from_string("[{% for s in nope %}{{ s }}{% endfor %}]").render() == "[]"
