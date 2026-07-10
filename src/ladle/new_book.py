#!/usr/bin/env python3
"""Scaffold a new book in ./<name>/ (relative to the current directory).

Creates <name>/book.yaml (minimal — only `title`; everything else falls back to
the theme's defaults) plus content/introduction.md and one ready-to-build example
recipe with a placeholder illustration, so `cd <name> && ladle build` produces a
complete, populated cookbook on the very first run. Nothing outside <name>/ is
touched.

Usage:
  ladle new [<name>] [--title ...] [--language ...] [--force]

`new` never prompts: anything not passed uses a default. <name> defaults to
`book`; the title defaults to the name in Title Case.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

import yaml

from . import ui

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# A tasteful, on-theme placeholder illustration (a steaming bowl in ink line-art)
# shipped with the scaffold so the first build renders a complete recipe page with
# no missing-asset warning. Drop a raster sibling (example-recipe.png) next to it
# to swap in real art with no front-matter change — see resolve_illustration().
EXAMPLE_ILLUSTRATION_SVG = """\
<svg xmlns="http://www.w3.org/2000/svg" viewBox="45 95 370 250">
  <ellipse cx="230" cy="288" rx="120" ry="16" fill="#000000" opacity="0.06"/>
  <ellipse cx="230" cy="210" rx="100" ry="20" fill="#fffdf7" stroke="#3a2f25" stroke-width="2.4"/>
  <path d="M 132 210 Q 230 300 328 210 Z" fill="#fdfaf3" stroke="#3a2f25" stroke-width="2.4" stroke-linejoin="round"/>
  <ellipse cx="230" cy="210" rx="100" ry="20" fill="#f0e6cf" opacity="0.55"/>
  <path d="M 205 150 q 12 -14 0 -28 q -12 -14 0 -28" fill="none" stroke="#cdbfa0" stroke-width="2.4" opacity="0.85"/>
  <path d="M 230 150 q 12 -14 0 -28 q -12 -14 0 -28" fill="none" stroke="#cdbfa0" stroke-width="2.4" opacity="0.85"/>
  <path d="M 255 150 q 12 -14 0 -28 q -12 -14 0 -28" fill="none" stroke="#cdbfa0" stroke-width="2.4" opacity="0.85"/>
</svg>
"""

# The optional book.yaml keys, shown commented so authors can discover and
# uncomment them — rather than pre-filling defaults that already come from the
# theme (see build_html: palette/fonts merge over the theme manifest).
OPTIONAL_KEYS = """
# subtitle: A short tagline shown on the cover
# volume: "1.0"
# rights: © {year} {title} contributors
# content_license: CC-BY-SA-4.0
# theme: default                    # a bundled theme name, or a path to your own theme dir
# sections: [Savory, Desserts, Beverages]   # Contents order; recipes group by their `category`
# order: []                         # explicit recipe order by slug; empty = by section, then title
# palette: {{navy: "#16203a", cream: "#faefdb"}}   # override individual theme colors
# fonts: {{display: Playfair Display, body: Bitter}}
"""


def render_book_yaml(title: str, language: str) -> str:
    """A minimal, valid book.yaml: the two active keys (safely quoted) + a
    commented block listing the optional overrides."""
    header = (
        f"# {title} — book-level configuration.\n"
        "# Only `title` is required; the rest falls back to the theme's defaults.\n"
        "# Uncomment a line below to override.\n"
    )
    active = yaml.safe_dump({"title": title, "language": language}, sort_keys=False, allow_unicode=True)
    optional = OPTIONAL_KEYS.format(year=datetime.date.today().year, title=title)
    return header + active + optional


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser(
        "ladle new",
        __doc__,
        "ladle new mybook",
        "ladle new pt --title 'Cozinha PT' --language pt",
    )
    ap.add_argument("name", nargs="?", default="book", help="book directory to create (default: book)")
    ap.add_argument("--title", help="cover title (default: the name in Title Case)")
    ap.add_argument("--language", default="en", help="ISO 639-1 code, e.g. 'en', 'pt' (default: en)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing ./<name>/")
    args = ap.parse_args(argv)

    name = args.name
    if not SLUG_RE.match(name):
        return ui.die(
            f"name must match {SLUG_RE.pattern!r}, got {name!r}",
            ui.USAGE,
            hint="use lowercase words separated by hyphens, e.g. my-book",
        )

    book_dir = Path.cwd() / name
    if book_dir.exists() and not args.force:
        return ui.die(f"{name}/ already exists", ui.ERROR, hint="pass --force to overwrite")

    title = args.title or name.replace("-", " ").title()
    language = args.language

    (book_dir / "recipes").mkdir(parents=True, exist_ok=True)
    (book_dir / "content").mkdir(parents=True, exist_ok=True)
    illustrations_dir = book_dir / "assets" / "illustrations" / "recipes"
    illustrations_dir.mkdir(parents=True, exist_ok=True)

    (book_dir / "book.yaml").write_text(render_book_yaml(title, language), encoding="utf-8")

    (book_dir / "content" / "introduction.md").write_text(
        f"""---
title: Introduction
from:
  name: ""
  org: ""
---

Welcome to *{title}* — replace this placeholder with your own story.
""",
        encoding="utf-8",
    )

    (illustrations_dir / "example-recipe.svg").write_text(EXAMPLE_ILLUSTRATION_SVG, encoding="utf-8")

    (book_dir / "recipes" / "example-recipe.md").write_text(
        """---
title: Example Recipe
slug: example-recipe
category: Desserts            # Savory | Desserts | Beverages
servings: "6 people"          # optional
credits: "Your name here"     # optional
illustration: assets/illustrations/recipes/example-recipe.svg  # swap in your own art (SVG/PNG)
draft: false                  # set true to leave a recipe out of the build
# optional: page, story, author:{name,org}, headshot, attribution, tags, license
---

## INGREDIENTS

- 1 example ingredient

## DIRECTIONS

1. Replace this file with your first real recipe, then run `ladle build` again.

## NOTES

- This example recipe builds as-is so your first cookbook isn't empty — edit or
  delete it once you've added your own.
""",
        encoding="utf-8",
    )

    ui.success(f"Scaffolded {name}/")
    ui.step("Next steps:")
    ui.step(f"  cd {name} && ladle build && ladle validate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
