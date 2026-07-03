"""Shared book.yaml config loader, imported by every build/validate tool.

Resolves which book.yaml a tool operates on: `--book PATH` CLI flag >
`BOOK_CONFIG` env var > `book.yaml` at the repo root (the backward-compatible
default every existing invocation keeps using). A relative `--book` path (or
the default `"book.yaml"`) resolves against REPO_ROOT, matching every other
tool in this repo, which already assumes cwd == REPO_ROOT.

A book's `recipes_dir` / `illustrations_dir` / `introduction` paths resolve
relative to *its own* book.yaml's directory (`BookConfig.root`), not
REPO_ROOT, so a book living anywhere (e.g. `books/pt/book.yaml`) works
without special-casing. Shared design assets (templates, fonts, CSS, the
navy pattern art) stay REPO_ROOT-scoped in every tool that uses them — they
are the visual identity, not book content, and are not made per-book here.
"""
from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class BookConfig:
    path: Path
    data: dict

    @property
    def root(self) -> Path:
        """Directory containing this book's book.yaml."""
        return self.path.parent

    @property
    def recipes_dir(self) -> Path:
        return self.root / self.data.get("recipes_dir", "recipes")

    @property
    def illustrations_dir(self) -> Path:
        return self.root / self.data.get("illustrations_dir", "assets/illustrations/recipes")

    @property
    def introduction_path(self) -> Path:
        return self.root / self.data.get("introduction", "content/introduction.md")


def add_book_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--book",
        metavar="PATH",
        default=None,
        help="Path to a book.yaml (default: $BOOK_CONFIG or the repo-root book.yaml)",
    )


def resolve_book_path(cli_value: str | None = None) -> Path:
    value = cli_value or os.environ.get("BOOK_CONFIG") or "book.yaml"
    path = Path(value)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


def load_book_config(cli_value: str | None = None) -> BookConfig:
    path = resolve_book_path(cli_value)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return BookConfig(path=path, data=data)
