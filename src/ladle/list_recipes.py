#!/usr/bin/env python3
"""List a book's recipes.

A data command: output goes to **stdout** — an aligned human table by default,
or ``--json`` / ``--plain`` for scripts. Reads each recipe's front matter and
orders them the way the book builds (by section, then explicit ``order:``, then
title), so the listing matches the table of contents.

Run: ladle list
"""
from __future__ import annotations

import json

from . import build_html, config, ui


def gather(book_cfg: config.BookConfig) -> list[dict]:
    """One record per recipe: ``{slug, title, category, draft, tags}``."""
    records: list[dict] = []
    for p in sorted(book_cfg.recipes_dir.glob("*.md")):
        fm, _ = build_html.split_front_matter(p.read_text(encoding="utf-8"))
        records.append({
            "slug": fm.get("slug") or p.stem,
            "title": fm.get("title", p.stem),
            "category": fm.get("category", ""),
            "draft": bool(fm.get("draft", False)),
            "tags": fm.get("tags", []) or [],
        })
    return records


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser(__doc__, "ladle list", "ladle list --category Desserts --plain")
    ap.add_argument("--category", help="only recipes in this category")
    ap.add_argument("--tag", help="only recipes carrying this tag")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    book_cfg = config.load_book_config(args.book)

    records = gather(book_cfg)
    if args.category:
        records = [r for r in records if r["category"] == args.category]
    if args.tag:
        records = [r for r in records if args.tag in r["tags"]]
    records = build_html.order_recipes(records, book_cfg.data)

    console = ui.get()
    if console.json:
        ui.data(json.dumps(records, indent=2))
    elif console.plain:
        for r in records:
            ui.data("\t".join([r["slug"], r["category"], r["title"]]))
    else:
        for r in records:
            draft = "  (draft)" if r["draft"] else ""
            ui.data(f"{r['slug']:<28} {r['category']:<10} {r['title']}{draft}")

    return ui.OK


if __name__ == "__main__":
    raise SystemExit(main())
