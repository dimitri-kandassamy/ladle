#!/usr/bin/env python3
"""Scaffold a new book in ./<name>/ (relative to the current directory).

Creates <name>/book.yaml (minimal — only `title`; everything else falls back to
the theme's defaults) plus content/introduction.md and one ready-to-build example
recipe with a placeholder illustration, so `cd <name> && ladle build` produces a
complete, populated cookbook on the very first run. Nothing outside <name>/ is
touched.

The name is used verbatim as the directory (`My Cookbook` -> `./My Cookbook/`,
`Café` -> `./Café/`); only path-unsafe names are rejected. `new` never prompts:
<name> defaults to `book` and the title defaults to the name, so any field not
passed falls back to a sensible default.
"""

from __future__ import annotations

import datetime
import shlex
import sys
from pathlib import Path

import yaml

from . import ui

# Characters and names that are illegal or unportable in a path segment. The name
# is kept verbatim as a directory (Café, 日本料理, My Cookbook are all fine on
# modern filesystems), so we reject only what would break a path or trip Windows.
_UNSAFE_CHARS = set('/\\<>:"|?*') | {chr(c) for c in range(32)}
_RESERVED_NAMES = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}


def check_name(name: str) -> str | None:
    """Return why *name* is unusable as a directory, or None if it's safe.

    The name becomes a directory verbatim, so this rejects only genuinely unsafe
    or unportable input — never stylistic choices like case, spaces, or script.
    """
    if not name:
        return "name is empty"
    if name in (".", ".."):
        return f"{name!r} is not a usable directory name"
    if _UNSAFE_CHARS & set(name):
        return 'name may not contain / \\ : * ? " < > | or control characters'
    if name.endswith("."):
        return "name may not end with '.'"
    if name.rsplit(".", 1)[0].lower() in _RESERVED_NAMES:
        return f"{name!r} is a reserved name on Windows"
    return None


def derive_title(raw: str) -> str:
    """A sensible default cover title from the name the user typed.

    A name written with spaces or capitals is already a human title, so keep it
    verbatim (``"My Cookbook"``, ``"Café"``). A slug (all-lowercase, hyphen- or
    underscore-separated) is prettified: ``the-ladle-kitchen`` -> ``The Ladle Kitchen``.
    """
    raw = raw.strip()
    if raw != raw.lower() or " " in raw:
        return raw
    return raw.replace("-", " ").replace("_", " ").title()


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
        "ladle new                       # -> ./book/",
        'ladle new the-ladle-kitchen     # -> ./the-ladle-kitchen/  (title "The Ladle Kitchen")',
        'ladle new "My Cookbook" --language fr',
    )
    ap.add_argument("name", nargs="?", default="book", help="book directory to create (default: book)")
    ap.add_argument("--title", help="cover title (default: derived from the name)")
    ap.add_argument("--language", default="en", help="ISO 639-1 language code (default: en)")
    ap.add_argument("--force", action="store_true", help="overwrite an existing directory")
    args = ap.parse_args(argv)

    name = args.name.strip()
    if err := check_name(name):
        return ui.die(err, ui.USAGE, hint="pick a name that works as a folder, e.g. my-book")

    book_dir = Path.cwd() / name
    if book_dir.exists() and not args.force:
        return ui.die(f"{name}/ already exists", ui.ERROR, hint="pass --force to overwrite")

    title = args.title or derive_title(name)
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
    ui.step(f"  cd {shlex.quote(name)} && ladle build && ladle validate")
    return 0


if __name__ == "__main__":
    sys.exit(main())
