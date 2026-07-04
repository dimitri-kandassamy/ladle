#!/usr/bin/env python3
"""Scaffold a new book under books/<name>/ (relative to the current directory).

Creates books/<name>/book.yaml, books/<name>/content/introduction.md, and a
single draft example recipe — enough to run `ladle build --book
books/<name>/book.yaml` immediately. Nothing outside books/<name>/ is touched.

Usage:
  ladle new --name pt [--title ...] [--subtitle ...] [--language pt]
                       [--palette-navy '#...'] [--palette-cream '#...'] [--force]

Any field not passed as a flag is prompted for interactively.
"""
from __future__ import annotations

import argparse
import datetime
import re
import sys
from pathlib import Path

import yaml

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


def prompt(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{label}{suffix}: ").strip()
    return value or default


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", help="lowercase, hyphenated book id, e.g. 'pt' -> books/pt/")
    ap.add_argument("--title")
    ap.add_argument("--subtitle")
    ap.add_argument("--language", help="ISO 639-1 code, e.g. 'en', 'pt'")
    ap.add_argument("--palette-navy", dest="palette_navy")
    ap.add_argument("--palette-cream", dest="palette_cream")
    ap.add_argument("--force", action="store_true", help="overwrite an existing books/<name>/")
    args = ap.parse_args(argv)

    name = args.name or prompt("Book name (lowercase, hyphenated, e.g. 'pt')")
    if not SLUG_RE.match(name or ""):
        print(f"error: --name must match {SLUG_RE.pattern!r}, got {name!r}", file=sys.stderr)
        return 1

    out_root = Path.cwd()
    book_dir = out_root / "books" / name
    if book_dir.exists() and not args.force:
        print(f"error: books/{name}/ already exists (use --force to overwrite)", file=sys.stderr)
        return 1

    title = args.title or prompt("Title", f"The {name.title()} Cookbook")
    subtitle = args.subtitle or prompt("Subtitle", "Stories & food from people who love to cook")
    language = args.language or prompt("Language code (ISO 639-1)", "en")

    palette = dict(DEFAULT_PALETTE)
    if args.palette_navy:
        palette["navy"] = args.palette_navy
    if args.palette_cream:
        palette["cream"] = args.palette_cream

    (book_dir / "recipes").mkdir(parents=True, exist_ok=True)
    (book_dir / "content").mkdir(parents=True, exist_ok=True)

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
        f"# {title} — book-level configuration.\n"
        + yaml.safe_dump(book_yaml, sort_keys=False, allow_unicode=True),
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

    (book_dir / "recipes" / "_example-recipe.md").write_text(
        """---
title: Example Recipe
slug: example-recipe
category: Desserts            # Savory | Desserts | Beverages
servings: "6 people"          # optional
credits: "Your name here"     # optional
illustration: assets/illustrations/recipes/example-recipe.svg
draft: true                   # remove this line once you replace the recipe
# optional: page, story, author:{name,org}, headshot, attribution, tags, license
---

## INGREDIENTS

- 1 example ingredient

## DIRECTIONS

1. Replace this file with your first real recipe.

## NOTES

- Optional notes go here.
""",
        encoding="utf-8",
    )

    print(f"Scaffolded books/{name}/")
    print("Next steps:")
    print(f"  ladle build --book books/{name}/book.yaml && ladle validate --book books/{name}/book.yaml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
