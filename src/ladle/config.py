"""Shared configuration + path resolution, imported by every build/validate tool.

Two kinds of path live here, and they resolve against different roots:

* **Tool/theme data** ships *inside* the installed package (`ladle/schema`,
  `ladle/themes/<name>/`). It resolves against ``PACKAGE_ROOT`` so it works
  identically whether ``ladle`` is run from a git checkout or ``pip install``ed
  into site-packages.
* **Book content + build output** belongs to the *user*, not the tool. A book's
  ``recipes_dir`` / ``illustrations_dir`` / ``introduction`` resolve against its
  own ``book.yaml`` directory (:pyattr:`BookConfig.root`); build artifacts land
  in :func:`build_dir` (relative to the current working directory). So a book
  living anywhere — the repo root, ``examples/``, or a stranger's own repo that
  merely ``pip install``ed this tool — works with no special-casing.

Which ``book.yaml`` a command operates on is resolved as:
``--book PATH`` flag  >  ``$BOOK_CONFIG``  >  ``book.yaml`` in the cwd.
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

import yaml

# Tool/theme data bundled in the package (works in a checkout and in site-packages).
PACKAGE_ROOT = Path(__file__).resolve().parent
THEMES_DIR = PACKAGE_ROOT / "themes"
SCHEMA_PATH = PACKAGE_ROOT / "schema" / "recipe.schema.json"


def build_dir() -> Path:
    """Directory built artifacts (HTML/PDF/EPUB/contact sheet) are written to.

    Relative to the cwd so it works both in this repo (cwd == repo root) and for
    someone who ``pip install``ed the tool and runs it from their own book
    directory. Override with ``$LADLE_BUILD``.
    """
    return Path(os.environ.get("LADLE_BUILD", "build")).resolve()


def epubcheck_jar() -> Path:
    """Path to the epubcheck jar for `validate` (optional; a structural fallback
    runs without it). Override with ``$EPUBCHECK_JAR``."""
    return Path(os.environ.get("EPUBCHECK_JAR", "tools/epubcheck/epubcheck.jar"))


def rel(path: Path) -> str:
    """A path for display: relative to the cwd when possible, else absolute."""
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


# Shape a theme.yaml is normalized to, so callers can rely on the keys existing.
_THEME_DEFAULTS: dict = {"name": "", "palette": {}, "fonts": {}, "font_faces": []}


def load_theme(theme_dir: Path) -> dict:
    """Load a theme's `theme.yaml` manifest (palette/fonts/font_faces defaults).

    A theme without a manifest still works — it just contributes no token
    defaults, so its book.yaml must supply palette/fonts itself.
    """
    manifest = theme_dir / "theme.yaml"
    data = {}
    if manifest.exists():
        data = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
    return {**_THEME_DEFAULTS, **data}


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    h = value.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


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

    @property
    def theme_dir(self) -> Path:
        """Design bundle (templates/css/fonts/patterns) this book renders with.

        A bare name (``theme: default``) resolves to a theme shipped in the
        package; a path (``theme: themes/mine``) resolves relative to the book,
        so a book can carry its own theme without touching the package.
        """
        theme = self.data.get("theme", "default")
        p = Path(theme)
        if len(p.parts) > 1 or p.is_absolute():
            return p if p.is_absolute() else (self.root / p)
        return THEMES_DIR / theme

    def theme_path(self, *parts: str) -> Path:
        return self.theme_dir.joinpath(*parts)

    def load_theme(self) -> dict:
        """This book's theme manifest (see :func:`load_theme`)."""
        return load_theme(self.theme_dir)


def add_book_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--book",
        metavar="PATH",
        default=None,
        help="Path to a book.yaml (default: $BOOK_CONFIG or ./book.yaml)",
    )


def resolve_book_path(cli_value: str | None = None) -> Path:
    value = cli_value or os.environ.get("BOOK_CONFIG") or "book.yaml"
    return Path(value).resolve()


class NoBookError(FileNotFoundError):
    """Raised when the resolved book.yaml does not exist (mapped to exit code 3)."""


def load_book_config(cli_value: str | None = None) -> BookConfig:
    path = resolve_book_path(cli_value)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise NoBookError(f"no book config found at {rel(path)}") from None
    data = yaml.safe_load(text) or {}
    return BookConfig(path=path, data=data)
