#!/usr/bin/env python3
"""Scaffold a new book in ./<name>/ (relative to the current directory).

Creates <name>/book.yaml, <name>/content/introduction.md, and one
ready-to-build example recipe with a placeholder illustration — so `cd <name> &&
ladle build` produces a real, populated cookbook (a filled Contents page and an
illustrated recipe spread) on the very first run, before the author edits
anything. Nothing outside <name>/ is touched.

Usage:
  ladle new --name pt [--title ...] [--subtitle ...] [--language pt]
                       [--palette-navy '#...'] [--palette-cream '#...'] [--force]

Any field not passed as a flag is prompted for interactively.
"""

from __future__ import annotations

import datetime
import re
import sys
from pathlib import Path

import yaml

from . import ui

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")

# Defaults for a new book's design tokens — the built-in `default` theme's
# palette and font pairing. A new book renders identically to the example until
# the author edits these.
DEFAULT_PALETTE = {
    "navy": "#16203a",
    "cream": "#faefdb",
    "ink": "#3c3c3c",
    "ink_deep": "#231f20",
    "rule": "#c9bfa6",
}
DEFAULT_FONTS = {"display": "Playfair Display", "body": "Bitter"}

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


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser("ladle new", __doc__, "ladle new --name pt --title 'Cozinha PT' --language pt")
    ap.add_argument("--name", help="lowercase, hyphenated book id, e.g. 'pt' -> ./pt/")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--language", help="ISO 639-1 code, e.g. 'en', 'pt'")
    ap.add_argument("--palette-navy", dest="palette_navy")
    ap.add_argument("--palette-cream", dest="palette_cream")
    ap.add_argument("--force", action="store_true", help="overwrite an existing ./<name>/")
    args = ap.parse_args(argv)

    # Prompt only on a real TTY and unless --no-input; otherwise take flag/default.
    interactive = sys.stdin.isatty() and not ui.get().no_input

    def ask(value: str | None, label: str, default: str = "") -> str:
        if value:
            return value
        return prompt(label, default) if interactive else default

    name = args.name
    if not name:
        if not interactive:
            return ui.die("--name is required", ui.USAGE, hint="pass --name SLUG (e.g. --name pt)")
        name = prompt("Book name (lowercase, hyphenated, e.g. 'pt')")
    if not SLUG_RE.match(name or ""):
        return ui.die(f"--name must match {SLUG_RE.pattern!r}, got {name!r}", ui.USAGE)

    out_root = Path.cwd()
    book_dir = out_root / name
    if book_dir.exists() and not args.force:
        return ui.die(f"{name}/ already exists", ui.ERROR, hint="pass --force to overwrite")

    title = ask(args.title, "Title", f"The {name.title()} Cookbook")
    subtitle = ask(args.subtitle, "Subtitle", "Stories & food from people who love to cook")
    language = ask(args.language, "Language code (ISO 639-1)", "en")

    palette = dict(DEFAULT_PALETTE)
    if args.palette_navy:
        palette["navy"] = args.palette_navy
    if args.palette_cream:
        palette["cream"] = args.palette_cream

    (book_dir / "recipes").mkdir(parents=True, exist_ok=True)
    (book_dir / "content").mkdir(parents=True, exist_ok=True)
    illustrations_dir = book_dir / "assets" / "illustrations" / "recipes"
    illustrations_dir.mkdir(parents=True, exist_ok=True)

    book_yaml = {
        "title": title,
        "subtitle": subtitle,
        "volume": "1.0",
        "language": language,
        "rights": f"© {datetime.date.today().year} {title} contributors",
        "content_license": "CC-BY-SA-4.0",
        "theme": "default",
        "palette": palette,
        "fonts": dict(DEFAULT_FONTS),
        "sections": ["Savory", "Desserts", "Beverages"],
        "order": [],
        "recipes_dir": "recipes",
        "illustrations_dir": "assets/illustrations/recipes",
        "introduction": "content/introduction.md",
    }
    (book_dir / "book.yaml").write_text(
        f"# {title} — book-level configuration.\n" + yaml.safe_dump(book_yaml, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

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
