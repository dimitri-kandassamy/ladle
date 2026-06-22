#!/usr/bin/env python3
"""Assemble recipes + book config into print HTML (Paged.js) and EPUB HTML (pandoc).

Single source of truth -> two renderers. Reads book.yaml + recipes/*.md, validates
front matter, parses each body into structured ingredients/directions/notes, and
renders templates/print.html.j2 -> build/cookbook.html and templates/epub.html.j2
-> build/epub.html.

Run: python3 tools/build_html.py
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, select_autoescape

ROOT = Path(__file__).resolve().parent.parent
RECIPES = ROOT / "recipes"
TEMPLATES = ROOT / "templates"
BUILD = ROOT / "build"
FONTS = ROOT / "assets" / "fonts"
CSS = ROOT / "assets" / "css"

ARTICLES = {"the", "a", "an"}

FONT_FACES = [
    ("Playfair Display", "PlayfairDisplay.ttf", "normal"),
    ("Playfair Display", "PlayfairDisplay-Italic.ttf", "italic"),
    ("Bitter", "Bitter.ttf", "normal"),
    ("Bitter", "Bitter-Italic.ttf", "italic"),
]


# ---- tiny, dependency-free inline markdown ---------------------------------
def inline(text: str) -> str:
    """Escape HTML then apply links, bold and italic. Good enough for recipe prose."""
    s = html.escape(text.strip())
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+)\)", r'<a href="\2">\1</a>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", s)
    return s


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


def resolve_illustration(path_str: str) -> str:
    """Prefer a raster sibling (real AI art) over the placeholder SVG.

    A recipe references e.g. `assets/illustrations/recipes/carrot-cake.svg`; if a
    `carrot-cake.png` exists alongside it (hand-generated artwork, see
    ILLUSTRATIONS.md), use that instead — so real art drops in with no front-matter edits.
    """
    if not path_str:
        return ""
    base = ROOT / path_str
    for ext in RASTER_EXTS:
        cand = base.with_suffix(ext)
        if cand.exists():
            return str(cand.relative_to(ROOT))
    return path_str


def asset_url(path_str: str, *, absolute: bool) -> str:
    """Resolve an asset path; absolute file:// for print, repo-relative for epub."""
    if not path_str:
        return ""
    p = (ROOT / path_str).resolve()
    if absolute:
        return p.as_uri() if p.exists() else (ROOT / path_str).as_uri()
    return path_str


def load_recipe(path: Path, *, absolute_assets: bool) -> dict:
    fm, body = split_front_matter(path.read_text(encoding="utf-8"))
    sec = sections_of(body)
    slug = fm.get("slug") or path.stem
    author = fm.get("author") or {}
    story = (fm.get("story") or "").strip()
    return {
        "slug": slug,
        "title": fm.get("title", slug),
        "category": fm.get("category", "Savory"),
        "servings": fm.get("servings", ""),
        "credits": plain_text(fm.get("credits", "")),
        "attribution": fm.get("attribution", ""),
        "has_story": bool(story),
        "story_html": paragraphs(story),
        "author": {"name": author.get("name", ""), "org": author.get("org", "")},
        "headshot_url": asset_url(fm.get("headshot", ""), absolute=absolute_assets),
        "illustration_url": asset_url(resolve_illustration(fm.get("illustration", "")), absolute=absolute_assets),
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


def load_intro(book: dict, *, absolute_assets: bool) -> dict:
    path = ROOT / book.get("introduction", "content/introduction.md")
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


def font_face_css() -> str:
    out = []
    for family, fname, style in FONT_FACES:
        uri = (FONTS / fname).as_uri()
        out.append(
            f'@font-face{{font-family:"{family}";'
            f'src:url("{uri}") format("truetype");'
            f"font-weight:100 900;font-style:{style};font-display:swap;}}"
        )
    return "\n".join(out)


def main() -> int:
    book = yaml.safe_load((ROOT / "book.yaml").read_text(encoding="utf-8"))
    book["title_article"], book["title_rest"] = split_title_article(book["title"])

    env = Environment(
        loader=FileSystemLoader(str(TEMPLATES)),
        autoescape=select_autoescape(["html"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    BUILD.mkdir(exist_ok=True)
    recipe_paths = sorted(RECIPES.glob("*.md"))

    # ---- print HTML (absolute file:// assets for Chrome) ----
    print_recipes = order_recipes(
        [load_recipe(p, absolute_assets=True) for p in recipe_paths], book
    )
    print_recipes = [r for r in print_recipes if not r["draft"]]
    print_html = env.get_template("print.html.j2").render(
        book=book,
        intro=load_intro(book, absolute_assets=True),
        recipes=print_recipes,
        font_face_css=font_face_css(),
        css_links=[(CSS / "common.css").as_uri(), (CSS / "print.css").as_uri()],
    )
    (BUILD / "cookbook.html").write_text(print_html, encoding="utf-8")

    # ---- EPUB HTML (repo-relative assets for pandoc) ----
    epub_recipes = order_recipes(
        [load_recipe(p, absolute_assets=False) for p in recipe_paths], book
    )
    epub_recipes = [r for r in epub_recipes if not r["draft"]]
    epub_html = env.get_template("epub.html.j2").render(
        book=book,
        intro=load_intro(book, absolute_assets=False),
        recipes=epub_recipes,
    )
    (BUILD / "epub.html").write_text(epub_html, encoding="utf-8")

    write_landing(book)

    print(f"Built build/cookbook.html and build/epub.html ({len(print_recipes)} recipes).")
    return 0


def write_landing(book: dict) -> None:
    """A small GitHub Pages download page linking the PDF + EPUB."""
    p = book["palette"]
    html_doc = f"""<!doctype html>
<html lang="{book['language']}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{book['title']}</title>
<style>
  body{{margin:0;font-family:Georgia,serif;background:{p['navy']};color:{p['cream']};
       min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center}}
  .card{{max-width:640px;padding:3rem 1.5rem}}
  h1{{font-size:3rem;line-height:1.05;margin:0 0 .3rem}} .the{{font-style:italic;font-weight:400}}
  p.sub{{text-transform:uppercase;letter-spacing:.16em;font-size:.8rem;opacity:.85}}
  .dl{{display:inline-block;margin:.5rem;padding:.8rem 1.6rem;border:1px solid {p['rule']};
       border-radius:4px;color:{p['cream']};text-decoration:none;letter-spacing:.08em}}
  .dl:hover{{background:rgba(255,255,255,.08)}}
  img{{max-width:100%;margin-top:2rem;border-radius:4px;opacity:.95}}
  .foot{{margin-top:2rem;font-size:.75rem;opacity:.6}}
</style></head><body><div class="card">
  <h1><span class="the">{book['title_article']}</span> {book['title_rest']}</h1>
  <p class="sub">{book['subtitle']} · Volume {book['volume']}</p>
  <div>
    <a class="dl" href="cookbook.pdf">Download PDF</a>
    <a class="dl" href="cookbook.epub">Download EPUB</a>
  </div>
  <a href="cookbook.pdf"><img src="contact-sheet.png" alt="Preview of all pages"></a>
  <p class="foot">{book['rights']} · <a href="{book['repo_url']}" style="color:{p['rule']}">Contribute a recipe</a></p>
</div></body></html>
"""
    (BUILD / "index.html").write_text(html_doc, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
