#!/usr/bin/env python3
"""Assemble recipes + book config into print HTML (WeasyPrint) and EPUB HTML (pandoc).

Single source of truth -> two renderers. Reads book.yaml + recipes/*.md, validates
front matter, parses each body into structured ingredients/directions/notes, and
renders the theme's print.html.j2 -> build/cookbook.html and epub.html.j2
-> build/epub.html.

The HTML stage of `ladle build` (not a standalone command).
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from jinja2 import FileSystemLoader, StrictUndefined, Undefined
from jinja2.exceptions import SecurityError, UndefinedError
from jinja2.sandbox import SandboxedEnvironment
from markupsafe import Markup

from . import config, ui

ARTICLES = {"the", "a", "an"}

# The theme's optional third template: a download page for the built book,
# rendered to build/index.html only when the theme ships one (see write_landing).
LANDING_TEMPLATE = "landing.html.j2"

# Where a recipe goes when its `category:` is missing, blank, or null. The schema
# requires the key, so `validate` fails such a book — but `build` still prints
# one, and it has to file those recipes somewhere. Assigned, never authored: it
# is deliberately not in the schema's enum, so a book cannot claim it directly.
#
# It is a bucket rather than a real category on purpose. Filing an uncategorised
# recipe under `Savory` was a guess the book had no basis for, and it put cakes
# in with the stews; this says only what is true, which is that nobody said.
FALLBACK_CATEGORY = "Uncategorized"

# Book chrome strings, overridable per-book via book.yaml's `labels:` block.
# `section_names` maps the internal category key (the enum Savory/Desserts/
# Beverages, plus FALLBACK_CATEGORY — front-matter matching keys, never
# translated) to a displayed name.
DEFAULT_LABELS = {
    "ingredients": "Ingredients",
    "directions": "Directions",
    "notes": "Notes",
    "yields": "Yields",
    "recipe_by": "Recipe by",
    "recipe_from": "Recipe from",
    "contents": "Contents",
    "from": "From",
    "volume": "Volume",
    "produced_by": "Edited & produced by",
    # Printed where the steps would be on a recipe whose author recorded only the
    # ingredients — a real shape in a hand-written archive, and one that reads as
    # an unfinished page unless the book says otherwise.
    "no_method": "No method was recorded for this recipe.",
    "section_names": {
        "Savory": "Savory",
        "Desserts": "Desserts",
        "Beverages": "Beverages",
        # Reads to a reader as a section the author chose, while the author gets
        # a warning per file and a failing `validate`. A book that would rather
        # say something else — or say nothing — overrides this one label.
        FALLBACK_CATEGORY: "Other Recipes",
    },
}


def merged_labels(book: dict) -> dict:
    """DEFAULT_LABELS with book.yaml's `labels:` block merged on top.

    An un-edited book.yaml (no `labels:` key) yields DEFAULT_LABELS unchanged,
    so this is backward compatible with every book that predates this feature.
    """
    labels = dict(DEFAULT_LABELS)
    labels["section_names"] = dict(DEFAULT_LABELS["section_names"])
    for key, value in (book.get("labels") or {}).items():
        if key == "section_names" and isinstance(value, dict):
            labels["section_names"].update(value)
        else:
            labels[key] = value
    return labels


# ---- tiny, dependency-free inline markdown ---------------------------------
def inline(text: str) -> Markup:
    """Escape HTML then apply links, bold and italic. Good enough for recipe prose.

    Returns a Markup so the pre-built <a>/<strong>/<em> tags render as-is
    through the now-autoescaping Jinja environment instead of being escaped
    again.
    """
    s = html.escape(text.strip())
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    # Internal cross-reference to another recipe by slug: `[Label](#slug)` links to
    # that recipe's anchor and is tagged `class="xref"` so a print theme can append
    # the target's resolved page number (target-counter) without the author baking
    # a folio into the text. In the EPUB it stays a plain hyperlink.
    s = re.sub(r"\[([^\]]+)\]\(#([a-z0-9][a-z0-9\-]*)\)", r'<a class="xref" href="#\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", s)
    return Markup(s)


def plain_text(text: str) -> str:
    """Flatten light markdown to plain text (for small-caps bylines/sidebars)."""
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text or "")
    s = re.sub(r"[*_`]", "", s)
    return s.strip()


def paragraphs(text: str) -> list[str]:
    text = (text or "").strip()
    if not text:
        return []
    blocks = re.split(r"\n\s*\n", text)
    out: list[str] = []
    for b in blocks:
        b = b.strip()
        if not b:
            continue
        # bullet list -> one paragraph per item
        if all(line.strip().startswith(("-", "*")) for line in b.splitlines()):
            for line in b.splitlines():
                out.append(inline(re.sub(r"^\s*[-*]\s+", "", line)))
        else:
            out.append(inline(" ".join(line.strip() for line in b.splitlines())))
    return out


# The markdown a recipe section body may use. Deliberately small and documented
# (README, "The body contract"): `###` sub-headings, `-`/`*` and `1.` lists, and
# the inline set `inline()` handles. Anything else renders as prose rather than
# being dropped — which is the whole point of rendering bodies instead of matching
# them against a line grammar.
_MD_H3 = re.compile(r"^\s{0,3}###\s+(.*\S)\s*$")
_MD_UL = re.compile(r"^\s*[-*]\s+(.*\S)\s*$")
_MD_OL = re.compile(r"^\s*\d+\.\s+(.*\S)\s*$")


def render_markdown(text: str) -> Markup:
    """Render a recipe section body to HTML.

    The single seam between recipe source and rendered output: one parse feeds
    both builds, because pandoc reads the EPUB HTML this produces. Swapping the
    in-repo renderer for a markdown library later means replacing this function
    and nothing else.

    Blocks are separated by blank lines. A non-blank line that starts no new
    block continues whatever is open — so a step wrapped onto a second line joins
    its step instead of being discarded, which is the failure this replaces.
    """
    out: list[str] = []
    para: list[str] = []
    items: list[str] = []
    tag = ""

    def flush() -> None:
        nonlocal tag
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()
        if items:
            body = "".join(f"<li>{inline(i)}</li>" for i in items)
            out.append(f"<{tag}>{body}</{tag}>")
            items.clear()
        tag = ""

    for line in (text or "").splitlines():
        if not line.strip():
            flush()
            continue
        if m := _MD_H3.match(line):
            flush()
            out.append(f"<h3>{inline(m.group(1))}</h3>")
            continue
        for pattern, kind in ((_MD_UL, "ul"), (_MD_OL, "ol")):
            if m := pattern.match(line):
                if para or tag != kind:
                    flush()
                tag = kind
                items.append(m.group(1))
                break
        else:
            # No marker. Continue the open list item or paragraph rather than
            # starting a block, matching markdown's lazy continuation.
            if items:
                items[-1] += " " + line.strip()
            else:
                para.append(line.strip())
    flush()
    return Markup("\n".join(out))


# ---- recipe parsing --------------------------------------------------------
def split_front_matter(raw: str, *, where: str = "") -> tuple[dict, str]:
    """Split `---` front matter from the body.

    An opening `---` with no closing one is a real authoring mistake (and used to
    surface as a raw ValueError), so it fails with a message naming the file
    rather than a traceback.
    """
    if not raw.startswith("---"):
        return {}, raw.strip()
    parts = raw.split("---", 2)
    if len(parts) < 3:
        label = f"{where}: " if where else ""
        raise config.ConfigError(f"{label}front matter is opened with '---' but never closed")
    _, fm, body = parts
    return yaml.safe_load(fm) or {}, body.strip()


def body_start_line(raw: str) -> int:
    """1-based line in *raw* where :func:`split_front_matter`'s body begins.

    Diagnostics report ``file:line`` so an author can jump straight to the
    offending line, which means the offset lost by stripping the front matter
    (and the blank lines after it) has to be recovered. Kept separate from
    :func:`split_front_matter` so the render path stays untouched.
    """
    parts = raw.split("---", 2)
    if raw.startswith("---") and len(parts) == 3:
        head, fm, body = parts
        consumed = f"{head}---{fm}---"
    else:
        consumed, body = "", raw
    lead = body[: len(body) - len(body.lstrip())]
    return consumed.count("\n") + lead.count("\n") + 1


# A body line paired with its 1-based line number in the source file.
Line = tuple[int, str]

# The `## HEADING`s the body parser understands. Content under any other heading
# is not rendered, so it is reported (see `unparsed_content`) rather than dropped.
KNOWN_SECTIONS = ("INGREDIENTS", "DIRECTIONS", "NOTES")

# Shared by the splitter and the diagnostics so "what counts as a heading" has
# exactly one definition.
HEADING_RE = re.compile(r"^##\s+(.*\S)\s*$")


def sections_of(body: str, *, start: int = 1) -> dict[str, list[Line]]:
    """Split a recipe body into `## HEADING` -> numbered lines.

    A heading repeated in one file accumulates rather than resetting, so the
    earlier block is not silently discarded.
    """
    out: dict[str, list[Line]] = {}
    current = None
    for offset, line in enumerate(body.splitlines()):
        m = HEADING_RE.match(line)
        if m:
            current = m.group(1).strip().upper()
            out.setdefault(current, [])
        elif current is not None:
            out[current].append((start + offset, line))
    return out


def section_text(lines: list[Line]) -> str:
    """Numbered lines back to plain text, for the prose sections."""
    return "\n".join(text for _, text in lines)


def extra_sections(sec: dict[str, list[Line]]) -> list[dict]:
    """Sections under a heading ladle does not know, rendered generically.

    A book written to another project's conventions will have headings ladle has
    never heard of. Rendering them as a titled block means nothing is dropped for
    being unrecognised, and themes need no per-heading slot contract: the build
    still warns (see :func:`unparsed_content`) so the author can rename them.

    Headings arrive uppercased from :func:`sections_of`; title case reads better
    in the EPUB, and the print theme's ``.label`` re-uppercases it anyway.
    """
    out: list[dict] = []
    for name, lines in sec.items():
        if name in KNOWN_SECTIONS:
            continue
        html = render_markdown(section_text(lines))
        if html:
            out.append({"title": name.title(), "html": html})
    return out


def split_title_article(title: str) -> tuple[str, str]:
    parts = title.split()
    if parts and parts[0].lower() in ARTICLES:
        return parts[0], " ".join(parts[1:])
    return "", title


RASTER_EXTS = (".png", ".webp", ".jpg", ".jpeg")


def resolve_illustration(path_str: str, *, book_root: Path) -> str:
    """Prefer a raster sibling (real AI art) over the placeholder SVG.

    A recipe references e.g. `assets/illustrations/recipes/carrot-cake.svg`; if a
    `carrot-cake.png` exists alongside it (hand-generated artwork, see DESIGN.md),
    use that instead — so real art drops in with no front-matter edits.
    """
    if not path_str:
        return ""
    base = book_root / path_str
    for ext in RASTER_EXTS:
        cand = base.with_suffix(ext)
        if cand.exists():
            return str(cand.relative_to(book_root))
    return path_str


def asset_url(path_str: str, *, absolute: bool, book_root: Path) -> str:
    """Resolve an asset path; absolute file:// for print, cwd-relative for epub.

    Pandoc (see make_epub, `--resource-path=".:<build>"`) resolves relative
    paths against the current working directory, so a book's asset is
    re-expressed relative to the cwd here — which is where `make_epub` runs
    pandoc — rather than left relative to book_root.
    """
    if not path_str:
        return ""
    p = (book_root / path_str).resolve()
    if absolute:
        return p.as_uri() if p.exists() else (book_root / path_str).as_uri()
    try:
        return str(p.relative_to(Path.cwd()))
    except ValueError:
        return path_str


def load_recipe(path: Path, *, absolute_assets: bool, book_root: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    fm, body = split_front_matter(raw, where=path.name)
    sec = sections_of(body, start=body_start_line(raw))
    slug = fm.get("slug") or path.stem
    author = fm.get("author") or {}
    story = (fm.get("story") or "").strip()
    credits = plain_text(fm.get("credits", ""))
    page = str(fm.get("page", "") or "").strip()
    if page:
        credits_line = f"{credits} (p. {page})" if credits else f"p. {page}"
    else:
        credits_line = credits
    return {
        "slug": slug,
        "title": fm.get("title", slug),
        # `or`, not a get() default: `category:` written blank or with no value
        # is present-but-unusable, and used to reach the page as an empty or
        # "None" section heading in the contents.
        "category": fm.get("category") or FALLBACK_CATEGORY,
        "servings": fm.get("servings", ""),
        "credits": credits,
        "page": page,
        "credits_line": credits_line,
        "attribution": fm.get("attribution", ""),
        "has_story": bool(story),
        "story_html": paragraphs(story),
        "author": {"name": author.get("name", ""), "org": author.get("org", "")},
        "headshot_url": asset_url(fm.get("headshot", ""), absolute=absolute_assets, book_root=book_root),
        "illustration_url": asset_url(
            resolve_illustration(fm.get("illustration", ""), book_root=book_root),
            absolute=absolute_assets,
            book_root=book_root,
        ),
        # Rendered HTML, not structured data. The keys are deliberately renamed
        # from `ingredient_groups`/`directions`: a theme still iterating the old
        # names now raises on an undefined variable instead of silently walking a
        # string one character at a time.
        "ingredients_html": render_markdown(section_text(sec.get("INGREDIENTS", []))),
        "directions_html": render_markdown(section_text(sec.get("DIRECTIONS", []))),
        "notes_html": render_markdown(section_text(sec.get("NOTES", []))),
        "extra_sections": extra_sections(sec),
        "draft": bool(fm.get("draft", False)),
    }


def order_recipes(recipes: list[dict], book: dict) -> list[dict]:
    sections = book.get("sections", [])
    explicit = {slug: i for i, slug in enumerate(book.get("order", []))}

    def key(r):
        sec_rank = sections.index(r["category"]) if r["category"] in sections else len(sections)
        ord_rank = explicit.get(r["slug"], 10_000)
        return (sec_rank, ord_rank, r["title"].lower())

    return sorted(recipes, key=key)


def build_toc(recipes: list[dict], book: dict) -> list[dict]:
    """*recipes* grouped into ordered sections, for the template to iterate.

    Templates get this derived structure rather than book.yaml's ``sections:``
    list, because that key is optional: looping over it directly printed an empty
    Contents page for every book that had not set it — silently, since Jinja
    iterates an undefined value as nothing.

    Declared sections come first and in their declared order. Any category no
    section declares follows, in the order the recipes already sort in, so a book
    with no ``sections:`` still gets one section per distinct category and every
    printed recipe keeps a contents entry.
    """
    labels = book["labels"]["section_names"]
    declared = book.get("sections") or []
    derived = [r["category"] for r in recipes if r["category"] not in declared]
    out = []
    for name in [*declared, *dict.fromkeys(derived)]:
        items = [r for r in recipes if r["category"] == name]
        if items:
            out.append({"name": name, "title": labels.get(name, name), "recipes": items})
    return out


def load_intro(book: dict, *, absolute_assets: bool, book_root: Path) -> dict:
    path = book_root / book.get("introduction", "content/introduction.md")
    if not path.exists():
        return {"title": "Introduction", "from_name": "", "from_org": "", "body_html": []}
    fm, body = split_front_matter(path.read_text(encoding="utf-8"), where=config.rel(path))
    frm = fm.get("from") or {}
    return {
        "title": fm.get("title", "Introduction"),
        "from_name": frm.get("name", ""),
        "from_org": frm.get("org", ""),
        "body_html": paragraphs(body),
    }


# Characters that must not reach a `<style>` element verbatim. `"` and `\` would
# break out of the CSS string; `<` could close the element early (`</style>`) and
# turn a theme manifest into markup. A theme is untrusted data (see make_env), and
# font_face_css is marked safe, so it does its own escaping rather than leaning on
# the autoescaper it opts out of.
_CSS_ESCAPES = {'"': r"\22 ", "\\": r"\5c ", "<": r"\3c ", "\n": r"\a ", "\r": r"\d "}


def css_string(value: str) -> str:
    """Escape *value* for use inside a double-quoted CSS string."""
    return "".join(_CSS_ESCAPES.get(ch, ch) for ch in value)


def font_face_css(fonts_dir: Path, font_faces: list[dict]) -> Markup:
    """The theme's `@font-face` rules, for the template's inline <style> block.

    Returns Markup, and that is load-bearing. The environment autoescapes, and a
    `<style>` element is raw text: a browser (and WeasyPrint) does *not* decode
    HTML entities inside it. Escaped, `url("…")` becomes `url(&#34;…&#34;)` —
    an invalid URL token — so every face is dropped and the book silently sets in
    whatever fallback font the machine happens to have. Fonts are the theme's,
    embedded in the PDF, so that failure is invisible and machine-dependent.
    """
    out = []
    for face in font_faces:
        uri = (fonts_dir / face["file"]).as_uri()
        style = face.get("style", "normal")
        out.append(
            f'@font-face{{font-family:"{css_string(face["family"])}";'
            f'src:url("{uri}") format("truetype");'
            f"font-weight:100 900;font-style:{style};font-display:swap;}}"
        )
    return Markup("\n".join(out))


@dataclass(frozen=True)
class Dropped:
    """One problem in a recipe file, reported as ``file:line: message``.

    Named for its first use — body content that will not appear in the built book
    — and since reused for a cross-reference that resolves to nothing, which does
    render but lands nowhere.
    """

    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


def excerpt(text: str, limit: int = 60) -> str:
    """A single-line, length-capped quote of *text* for a diagnostic."""
    s = " ".join(text.split())
    return s if len(s) <= limit else f"{s[: limit - 1]}…"


def unparsed_content(path: Path) -> list[Dropped]:
    """Body content in *path* that lands somewhere the author probably didn't mean.

    Now that section bodies render as markdown, no *line* can go unrendered — the
    per-line checks over INGREDIENTS/DIRECTIONS are gone with the line grammar
    they policed. What remains is structural, and both cases still render their
    content rather than dropping it:

    * text before the first ``##`` heading, which belongs to no section and so
      appears in no template slot;
    * a heading ladle does not know, which renders as a generic titled block
      instead of the section the author intended (see :func:`extra_sections`).

    Blank lines are not content and are never reported.
    """
    raw = path.read_text(encoding="utf-8")
    _, body = split_front_matter(raw, where=path.name)
    start = body_start_line(raw)
    sec = sections_of(body, start=start)
    out: list[Dropped] = []

    for offset, line in enumerate(body.splitlines()):
        if HEADING_RE.match(line):
            break
        if line.strip():
            out.append(
                Dropped(
                    path.name,
                    start + offset,
                    f'text before the first "##" heading is not rendered: "{excerpt(line)}"',
                )
            )

    for name, lines in sec.items():
        if name in KNOWN_SECTIONS:
            continue
        content = [(n, line) for n, line in lines if line.strip()]
        if content:
            known = ", ".join(KNOWN_SECTIONS)
            out.append(
                Dropped(
                    path.name,
                    content[0][0],
                    f'"## {name}" is not a section ladle knows ({known}) — '
                    f"rendered as a generic block, {len(content)} line"
                    f"{'s' if len(content) != 1 else ''}",
                )
            )
    return sorted(out, key=lambda d: d.line)


# The target half of the `[Label](#slug)` cross-reference `inline()` renders.
# Kept beside the check rather than shared with `inline()`: that one has to match
# the label to rewrite it, this one only needs the slug.
_XREF_RE = re.compile(r"\[[^\]]+\]\(#([a-z0-9][a-z0-9\-]*)\)")


def unresolved_xrefs(paths: list[Path]) -> list[Dropped]:
    """Cross-references that point at no recipe the built book will contain.

    A `[Label](#slug)` naming nothing still renders, as a link to nowhere: silent
    in the PDF, but an epubcheck error (RSC-012) in the EPUB — and epubcheck names
    the generated chapter file and column, not the recipe the author wrote. This
    trades that for a source line, before either build runs.

    Whole files are scanned, front matter included, because `story:` renders
    through the same inline markdown as the body. A draft is not a valid target:
    it is filtered out of both builds, so its anchor never exists — worth its own
    message, since the slug is right there in the recipes folder.
    """
    texts: dict[Path, str] = {}
    live: set[str] = set()
    drafts: set[str] = set()
    for p in paths:
        text = p.read_text(encoding="utf-8")
        texts[p] = text
        try:
            fm, _ = split_front_matter(text, where=p.name)
        except config.ConfigError:
            continue  # unsplittable front matter — already reported by the schema check
        (drafts if fm.get("draft", False) else live).add(fm.get("slug") or p.stem)

    out: list[Dropped] = []
    for p, text in texts.items():
        for n, line in enumerate(text.splitlines(), start=1):
            for slug in _XREF_RE.findall(line):
                if slug in live:
                    continue
                why = f'"{slug}" is a draft recipe' if slug in drafts else f'no recipe has the slug "{slug}"'
                out.append(Dropped(p.name, n, f"cross-reference to #{slug} resolves to nothing — {why}"))
    return out


def warn_unresolved_xrefs(recipes_dir: Path, *, limit: int = 10) -> None:
    """Warn about dead cross-references at build time, capped like its sibling."""
    found = unresolved_xrefs(sorted(recipes_dir.glob("*.md")))
    for d in found[:limit]:
        ui.warn(str(d))
    if len(found) > limit:
        n = len(found) - limit
        ui.warn(f"… and {n} more unresolved cross-reference{'s' if n != 1 else ''}.")


def warn_unparsed_content(recipes_dir: Path, *, limit: int = 10) -> None:
    """Warn about dropped body content at build time, capped so it stays readable.

    A build should say what it threw away, but a large import can produce dozens
    of these; past *limit* it summarises and points at ``validate`` for the full
    list — the same shape a compiler uses for repeated diagnostics.
    """
    found = [d for p in sorted(recipes_dir.glob("*.md")) for d in unparsed_content(p)]
    for d in found[:limit]:
        ui.warn(str(d))
    if len(found) > limit:
        ui.warn(f"… and {len(found) - limit} more — run `ladle validate` to see all of them.")


def warn_schema_issues(recipes_dir: Path) -> None:
    """Emit a stderr warning per schema-invalid recipe, without failing the build.

    Reuses ``validate.check_recipes`` so ``build`` and ``validate`` judge recipes
    identically. Imported locally to keep this module standalone-importable.
    """
    from . import validate

    for r in validate.check_recipes(recipes_dir):
        if r["ok"] or not r["file"]:  # skip passes and the synthetic "no recipes" record
            continue
        loc = f":{r['loc']}" if r["loc"] else ""
        ui.warn(f"{r['file']}{loc} {r['message']}")


def make_env(templates_dir: Path, *, strict: bool = False) -> SandboxedEnvironment:
    """Jinja environment for theme templates.

    Sandboxed on purpose: a theme is untrusted *data*, never code. Community
    themes ship executable Jinja, so rendering runs in a `SandboxedEnvironment`
    that blocks private-attribute access, imports, and unsafe callables. The
    bundled default theme stays well within these limits.

    *strict* turns a reference to something the core never passed into a named
    error instead of a blank region on the page. It is on for the themes we ship
    (where a typo is our bug to catch) and off for everyone else's, because it
    would fail themes written against today's looser contract; it becomes the
    single behaviour once themes declare an API version.
    """
    return SandboxedEnvironment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        undefined=StrictUndefined if strict else Undefined,
    )


def render_template(env: SandboxedEnvironment, name: str, **context: object) -> str:
    """Render a theme template, turning a sandbox trip into a friendly error."""
    try:
        return env.get_template(name).render(**context)
    except SecurityError as e:
        raise config.ConfigError(
            f"theme template {name} was blocked by the sandbox: {e}. Themes may not "
            "access private attributes, imports, or unsafe callables."
        ) from e
    except UndefinedError as e:
        raise config.ConfigError(
            f"theme template {name} used something the build does not provide: {e}. "
            "Templates read the context the core passes them (book, intro, recipes, toc), "
            "never book.yaml directly."
        ) from e


def render(book_path: str | None = None) -> int:
    """Render build/cookbook.html (print) and build/epub.html (semantic)."""
    book_cfg = config.load_book_config(book_path)
    book = book_cfg.data
    if not book.get("title"):
        raise config.ConfigError(f"{config.rel(book_cfg.path)} is missing required field: title")
    book_root = book_cfg.root
    theme = book_cfg.require_theme_dir()
    theme_manifest = config.load_theme(theme)
    templates_dir = theme / "templates"
    fonts_dir = theme / "fonts"
    css_dir = theme / "css"
    build = config.build_dir()
    # Theme tokens are defaults; book.yaml overrides any key. So a minimal book
    # (no palette/fonts) still renders with the theme's look.
    book["palette"] = {**theme_manifest.get("palette", {}), **(book.get("palette") or {})}
    book["fonts"] = {**theme_manifest.get("fonts", {}), **(book.get("fonts") or {})}
    # Optional top-level book metadata defaults, so a minimal book.yaml (just a
    # title) builds without KeyErrors in the templates / landing page.
    for key in ("subtitle", "producer", "rights", "repo_url"):
        book.setdefault(key, "")
    book.setdefault("volume", "")
    book.setdefault("language", "en")
    # Off unless asked for: a divider earns its sheet in a long book and crowds a
    # short one, and only the author knows which they are writing.
    book.setdefault("section_openers", False)
    book["title_article"], book["title_rest"] = split_title_article(book["title"])
    book["labels"] = merged_labels(book)

    env = make_env(templates_dir, strict=config.is_bundled_theme(theme))
    build.mkdir(parents=True, exist_ok=True)
    recipe_paths = sorted(book_cfg.recipes_dir.glob("*.md"))

    # Surface schema problems the build itself tolerates (a bad category renders
    # anyway; a missing title silently falls back to the slug). Warn, don't fail —
    # `ladle validate` is the hard gate. (#4)
    warn_schema_issues(book_cfg.recipes_dir)
    # Body content no parser rule claimed renders as nothing at all, and a
    # half-eaten step still *looks* complete on the page — so say so here rather
    # than letting a silently-wrong book get printed.
    warn_unparsed_content(book_cfg.recipes_dir)
    # A dead cross-reference is the one body problem that fails a later command
    # instead of this one (epubcheck RSC-012), so name it here in the author's
    # own file while there is still a source line to point at.
    warn_unresolved_xrefs(book_cfg.recipes_dir)

    # ---- print HTML (absolute file:// assets for WeasyPrint) ----
    print_recipes = order_recipes(
        [load_recipe(p, absolute_assets=True, book_root=book_root) for p in recipe_paths], book
    )
    print_recipes = [r for r in print_recipes if not r["draft"]]
    print_html = render_template(
        env,
        "print.html.j2",
        book=book,
        intro=load_intro(book, absolute_assets=True, book_root=book_root),
        recipes=print_recipes,
        toc=build_toc(print_recipes, book),
        font_face_css=font_face_css(fonts_dir, theme_manifest["font_faces"]),
        css_links=[(css_dir / "common.css").as_uri(), (css_dir / "print.css").as_uri()],
    )
    (build / "cookbook.html").write_text(print_html, encoding="utf-8")

    # ---- EPUB HTML (repo-relative assets for pandoc) ----
    epub_recipes = order_recipes(
        [load_recipe(p, absolute_assets=False, book_root=book_root) for p in recipe_paths], book
    )
    epub_recipes = [r for r in epub_recipes if not r["draft"]]
    epub_html = render_template(
        env,
        "epub.html.j2",
        book=book,
        intro=load_intro(book, absolute_assets=False, book_root=book_root),
        recipes=epub_recipes,
        # Unused by the bundled epub template (pandoc derives its own navigation
        # from the headings), but part of the context every template gets: a
        # theme that wants to print its sections should not have to re-derive them.
        toc=build_toc(epub_recipes, book),
    )
    (build / "epub.html").write_text(epub_html, encoding="utf-8")

    write_landing(env, templates_dir, book, build)

    n = len(print_recipes)
    ui.success(
        f"Built {config.rel(build / 'cookbook.html')} and "
        f"{config.rel(build / 'epub.html')} ({n} recipe{'s' if n != 1 else ''})."
    )
    return 0


def write_landing(env: SandboxedEnvironment, templates_dir: Path, book: dict, build: Path) -> None:
    """Render the theme's optional landing page to build/index.html.

    A download page for publishing the built book to GitHub Pages. It is the
    theme's to design and the theme's to opt into: a theme that ships no
    `landing.html.j2` simply gets no landing page, and that is not an error.

    The core used to build this page from an f-string that indexed the palette
    by name — `navy`, `cream`, `rule` — which are the bundled theme's token
    names and nothing more. A theme that called its ground something else died
    here with `error: 'navy'`, after both HTML files had already been written.
    A page whose design is a palette away from the book belongs with the rest of
    the design.
    """
    if not (templates_dir / LANDING_TEMPLATE).exists():
        return
    html_doc = render_template(env, LANDING_TEMPLATE, book=book)
    # Jinja drops one trailing newline from a template's source; this file is
    # published as-is rather than fed to another tool, so it keeps the one a text
    # file should end with.
    (build / "index.html").write_text(html_doc.rstrip("\n") + "\n", encoding="utf-8")
