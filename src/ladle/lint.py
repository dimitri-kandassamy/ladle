#!/usr/bin/env python3
"""Validate every recipe's front matter against the schema.

A data command: results go to **stdout** (human table by default, or ``--json`` /
``--plain`` for scripts). Split out of ``validate`` so a fast, toolchain-free
schema check can run on its own. Exit code 4 if any recipe fails.

Run: ladle lint
"""

from __future__ import annotations

import json

from . import config, ui, validate


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser("ladle lint", __doc__, "ladle lint --json | jq '.[] | select(.ok|not)'")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    book_cfg = config.load_book_config(args.book)

    results = validate.check_recipes(book_cfg.recipes_dir)
    console = ui.get()

    if console.json:
        ui.data(json.dumps(results, indent=2))
    elif console.plain:
        for r in results:
            status = "ok" if r["ok"] else "error"
            ui.data("\t".join([r["file"], status, r["loc"], r["message"]]))
    else:
        for r in results:
            if r["ok"]:
                ui.data(f"ok    {r['file']}")
            else:
                ui.data(f"error {validate._format_result(r)}")

    return ui.OK if all(r["ok"] for r in results) else ui.VALIDATION


if __name__ == "__main__":
    raise SystemExit(main())
