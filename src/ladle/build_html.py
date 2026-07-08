#!/usr/bin/env python3
"""Assemble recipes + book config into print HTML (WeasyPrint) and EPUB HTML (pandoc).

Single source of truth -> two renderers. Reads book.yaml + recipes/*.md, validates
front matter, parses each body into structured ingredients/directions/notes, and
renders the theme's print.html.j2 -> build/cookbook.html and epub.html.j2
-> build/epub.html.

Run: ladle html
"""

from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader
from markupsafe import Markup

from . import config, ui

ARTICLES = {"the", "a", "an"}

# Book chrome strings, overridable per-book via book.yaml's `labels:` block.
# `section_names` maps the internal category enum (Savory/Desserts/Beverages —
# the front-matter matching key, never translated) to a displayed name.
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
    "section_names": {
        "Savory": "Savory",
        "Desserts": "Desserts",
        "Beverages": "Beverages",
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


# ---- recipe parsing --------------------------------------------------------
def split_front_matter(raw: str) -> tuple[dict, str]:
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        return yaml.safe_load(fm) or {}, body.strip()
    return {}, raw.strip()


def sections_of(body: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    current = None
    for line in body.splitlines():
        m = re.match(r"^##\s+(.*\S)\s*$", line)
        if m:
            current = m.group(1).strip().upper()
            out[current] = []
        elif current is not None:
            out[current].append(line)
    return out


def parse_ingredients(lines: list[str]) -> list[dict]:
    groups: list[dict] = []
    current = {"label": "", "lines": []}
    for line in lines:
        h = re.match(r"^###\s+(.*\S)\s*$", line)
        item = re.match(r"^\s*[-*]\s+(.*\S)\s*$", line)
        if h:
            if current["lines"]:
                groups.append(current)
            current = {"label": h.group(1).strip(), "lines": []}
        elif item:
            current["lines"].append(inline(item.group(1)))
    if current["lines"]:
        groups.append(current)
    return groups


def parse_directions(lines: list[str]) -> list[str]:
    steps: list[str] = []
    for line in lines:
        m = re.match(r"^\s*\d+\.\s+(.*\S)\s*$", line)
        if m:
            steps.append(inline(m.group(1)))
    return steps


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
    fm, body = split_front_matter(path.read_text(encoding="utf-8"))
    sec = sections_of(body)
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
        "category": fm.get("category", "Savory"),
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
        "ingredient_groups": parse_ingredients(sec.get("INGREDIENTS", [])),
        "directions": parse_directions(sec.get("DIRECTIONS", [])),
        "notes_html": paragraphs("\n".join(sec.get("NOTES", []))),
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


def load_intro(book: dict, *, absolute_assets: bool, book_root: Path) -> dict:
    path = book_root / book.get("introduction", "content/introduction.md")
    if not path.exists():
        return {"title": "Introduction", "from_name": "", "from_org": "", "body_html": []}
    fm, body = split_front_matter(path.read_text(encoding="utf-8"))
    frm = fm.get("from") or {}
    return {
        "title": fm.get("title", "Introduction"),
        "from_name": frm.get("name", ""),
        "from_org": frm.get("org", ""),
        "body_html": paragraphs(body),
    }


def font_face_css(fonts_dir: Path, font_faces: list[dict]) -> str:
    out = []
    for face in font_faces:
        uri = (fonts_dir / face["file"]).as_uri()
        style = face.get("style", "normal")
        out.append(
            f'@font-face{{font-family:"{face["family"]}";'
            f'src:url("{uri}") format("truetype");'
            f"font-weight:100 900;font-style:{style};font-display:swap;}}"
        )
    return "\n".join(out)


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


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser("ladle html", __doc__, "ladle html --book books/pt/book.yaml")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    book_cfg = config.load_book_config(args.book)
    book = book_cfg.data
    if not book.get("title"):
        raise config.ConfigError(f"{config.rel(book_cfg.path)} is missing required field: title")
    book_root = book_cfg.root
    theme = book_cfg.theme_dir
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
    book["title_article"], book["title_rest"] = split_title_article(book["title"])
    book["labels"] = merged_labels(book)

    env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    build.mkdir(parents=True, exist_ok=True)
    recipe_paths = sorted(book_cfg.recipes_dir.glob("*.md"))

    # Surface schema problems the build itself tolerates (a bad category renders
    # anyway; a missing title silently falls back to the slug). Warn, don't fail —
    # `ladle validate` is the hard gate. (#4)
    warn_schema_issues(book_cfg.recipes_dir)

    # ---- print HTML (absolute file:// assets for WeasyPrint) ----
    print_recipes = order_recipes(
        [load_recipe(p, absolute_assets=True, book_root=book_root) for p in recipe_paths], book
    )
    print_recipes = [r for r in print_recipes if not r["draft"]]
    print_html = env.get_template("print.html.j2").render(
        book=book,
        intro=load_intro(book, absolute_assets=True, book_root=book_root),
        recipes=print_recipes,
        font_face_css=font_face_css(fonts_dir, theme_manifest["font_faces"]),
        css_links=[(css_dir / "common.css").as_uri(), (css_dir / "print.css").as_uri()],
    )
    (build / "cookbook.html").write_text(print_html, encoding="utf-8")

    # ---- EPUB HTML (repo-relative assets for pandoc) ----
    epub_recipes = order_recipes(
        [load_recipe(p, absolute_assets=False, book_root=book_root) for p in recipe_paths], book
    )
    epub_recipes = [r for r in epub_recipes if not r["draft"]]
    epub_html = env.get_template("epub.html.j2").render(
        book=book,
        intro=load_intro(book, absolute_assets=False, book_root=book_root),
        recipes=epub_recipes,
    )
    (build / "epub.html").write_text(epub_html, encoding="utf-8")

    write_landing(book, build)

    n = len(print_recipes)
    ui.success(
        f"Built {config.rel(build / 'cookbook.html')} and "
        f"{config.rel(build / 'epub.html')} ({n} recipe{'s' if n != 1 else ''})."
    )
    return 0


def write_landing(book: dict, build: Path) -> None:
    """A small GitHub Pages download page linking the PDF + EPUB."""
    p = book["palette"]
    html_doc = f"""<!doctype html>
<html lang="{book["language"]}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{book["title"]}</title>
<style>
  body{{margin:0;font-family:Georgia,serif;background:{p["navy"]};color:{p["cream"]};
       min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center}}
  .card{{max-width:640px;padding:3rem 1.5rem}}
  h1{{font-size:3rem;line-height:1.05;margin:0 0 .3rem}} .the{{font-style:italic;font-weight:400}}
  p.sub{{text-transform:uppercase;letter-spacing:.16em;font-size:.8rem;opacity:.85}}
  .dl{{display:inline-block;margin:.5rem;padding:.8rem 1.6rem;border:1px solid {p["rule"]};
       border-radius:4px;color:{p["cream"]};text-decoration:none;letter-spacing:.08em}}
  .dl:hover{{background:rgba(255,255,255,.08)}}
  img{{max-width:100%;margin-top:2rem;border-radius:4px;opacity:.95}}
  .foot{{margin-top:2rem;font-size:.75rem;opacity:.6}}
</style></head><body><div class="card">
  <h1><span class="the">{book["title_article"]}</span> {book["title_rest"]}</h1>
  <p class="sub">{book["subtitle"]} · Volume {book["volume"]}</p>
  <div>
    <a class="dl" href="cookbook.pdf">Download PDF</a>
    <a class="dl" href="cookbook.epub">Download EPUB</a>
  </div>
  <a href="cookbook.pdf"><img src="contact-sheet.png" alt="Preview of all pages"></a>
  <p class="foot">{book["rights"]} · <a href="{book["repo_url"]}" style="color:{p["rule"]}">Contribute a recipe</a></p>
</div></body></html>
"""
    (build / "index.html").write_text(html_doc, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
