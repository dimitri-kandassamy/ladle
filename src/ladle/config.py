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
``--book PATH`` flag  >  ``book.yaml`` in the cwd.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

import jsonschema
import yaml

from . import ui

# Tool/theme data bundled in the package (works in a checkout and in site-packages).
PACKAGE_ROOT = Path(__file__).resolve().parent
THEMES_DIR = PACKAGE_ROOT / "themes"
# Canonical sample book (shipped in the package) rendered by `ladle theme preview`.
SAMPLE_BOOK = PACKAGE_ROOT / "sample" / "book.yaml"
SCHEMA_PATH = PACKAGE_ROOT / "schema" / "recipe.schema.json"
BOOK_SCHEMA_PATH = PACKAGE_ROOT / "schema" / "book.schema.json"
THEME_SCHEMA_PATH = PACKAGE_ROOT / "schema" / "theme.schema.json"


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


class NoBookError(FileNotFoundError):
    """Raised when the resolved book.yaml does not exist (mapped to exit code 3)."""


class ConfigError(Exception):
    """A config file (book.yaml or a theme's theme.yaml) that exists but is unusable
    (bad YAML, wrong shape, or a missing required field). Carries a one-line,
    user-facing message; dispatch turns it into a clean ``error: …`` instead of a
    traceback."""


class ThemeNotFoundError(ConfigError):
    """A `theme:` reference that resolves to no directory.

    Its own type only so dispatch can skip the "check the file's syntax" hint —
    the syntax is fine, the theme is somewhere else — and because the message
    already lists every directory that was searched.
    """


# ---- the theme manifest ----------------------------------------------------
# Which manifest namespaces a book.yaml may override key by key, and which belong
# to the theme alone. This pair is the precedence contract in one place: the merge
# in build_html loops the first, `theme lint` and `validate` read the second, and
# docs/THEMING.md's table is asserted against both. It used to live only in prose
# and in the shape of build_html.render, which is how a documented per-key palette
# override came to silently not reach the PDF.
OVERRIDABLE_NAMESPACES = ("palette", "fonts", "params", "labels")
THEME_OWNED_NAMESPACES = ("page", "stylesheets", "templates")

# The output targets a theme declares a template (and stylesheets) for. `landing`
# is optional; see :meth:`ThemeManifest.template`.
PRINT, EPUB, LANDING = "print", "epub", "landing"

# Shape a theme.yaml is normalized to, so callers can rely on the keys existing.
# Every default is the value the core hardcoded *before* the manifest could
# declare it, so a theme predating these keys renders exactly as it did.
_THEME_DEFAULTS: dict = {
    "name": "",
    "page": {"trim": ["6.75in", "9.5in"]},
    "stylesheets": {PRINT: ["css/common.css", "css/print.css"], EPUB: ["css/epub.css"]},
    "templates": {PRINT: "print.html.j2", EPUB: "epub.html.j2", LANDING: "landing.html.j2"},
    "palette": {},
    "fonts": {},
    "params": {},
    "labels": {},
    "font_faces": [],
    "fonts_meta": [],
}


def _normalize_theme(data: dict) -> dict:
    """*data* with every defaulted key present, filled one nested key at a time.

    Per key, not per namespace. ``{**_THEME_DEFAULTS, **data}`` is shallow, which
    was harmless only while every default was empty: the moment ``templates`` has
    real defaults, a theme declaring one sub-key — ``templates: {print: mine.j2}``
    — would lose the epub and landing defaults and fail the build on a template
    nobody named.
    """
    out = dict(data)
    for key, default in _THEME_DEFAULTS.items():
        value = data.get(key)
        if isinstance(default, dict):
            out[key] = {**default, **(value or {})}
        else:
            out[key] = default if value is None else value
    return out


@dataclass(frozen=True)
class ThemeManifest:
    """A theme's `theme.yaml`, normalized, together with the directory it came from.

    The manifest and its directory travel together because every path the manifest
    names resolves against that directory — and because the alternative is what
    this replaces: ``theme / "css" / "epub.css"`` and its siblings hardcoded at
    each call site, which is exactly the layout assumption the manifest exists to
    remove. It also leaves one seam for a future override resolver to hook, rather
    than one per caller (see :meth:`path`).
    """

    dir: Path
    data: dict = field(default_factory=dict)  # normalized: every defaulted key present
    raw: dict = field(default_factory=dict)  # as written, so `declared` can spot a default

    @classmethod
    def defaults(cls, theme_dir: Path) -> ThemeManifest:
        """The manifest a theme with no readable theme.yaml gets: the core defaults.

        What the build falls back to, and what lets `theme lint` keep reporting on
        a theme whose manifest it could not load.
        """
        return cls(dir=theme_dir, data=_normalize_theme({}), raw={})

    # ---- identity + token namespaces ----
    @property
    def name(self) -> str:
        return str(self.data.get("name") or "")

    @property
    def title(self) -> str:
        return str(self.data.get("title") or self.name)

    @property
    def palette(self) -> dict:
        return self.data["palette"]

    @property
    def fonts(self) -> dict:
        return self.data["fonts"]

    @property
    def params(self) -> dict:
        return self.data["params"]

    @property
    def labels(self) -> dict:
        return self.data["labels"]

    @property
    def font_faces(self) -> list[dict]:
        return self.data["font_faces"]

    @property
    def fonts_meta(self) -> list[dict]:
        return self.data["fonts_meta"]

    @property
    def trim(self) -> list[str]:
        """Declared trim as ``[width, height]`` CSS lengths (see `page.trim`)."""
        return list(self.data["page"].get("trim") or [])

    @property
    def manifest_path(self) -> Path:
        return self.dir / "theme.yaml"

    @property
    def templates_dir(self) -> Path:
        return self.dir / "templates"

    @property
    def fonts_dir(self) -> Path:
        return self.dir / "fonts"

    # ---- paths the manifest names ----
    def declared(self, dotted: str) -> bool:
        """Was *dotted* actually written in theme.yaml, or is it a core default?

        Tells "this theme ships no landing page", which is a design choice, apart
        from "this theme names a landing template that is not there", a typo.
        """
        node: object = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return False
            node = node[part]
        return node is not None

    def path(self, relpath: str, *, key: str = "") -> Path:
        """A theme-relative path, guaranteed to stay inside the theme directory.

        A theme is untrusted *data*, never code (see ``build_html.make_env``).
        While the core hardcoded which files it loaded, a manifest had nothing to
        escape with; now that a theme names its own stylesheets,
        ``../../../etc/passwd`` would otherwise reach WeasyPrint as a `file://`
        URI. *key* names the manifest key at fault, since the path itself is
        rarely enough to find it.
        """
        where = f"{key}: " if key else ""
        text = (relpath or "").strip()
        if not text:
            raise ConfigError(f"{rel(self.manifest_path)}: {where}names an empty path")
        pure = PurePosixPath(text)
        if pure.is_absolute() or text.startswith("~") or "\\" in text or ":" in text:
            raise ConfigError(
                f"{rel(self.manifest_path)}: {where}{text!r} must be a relative path inside the theme directory"
            )
        if ".." in pure.parts:
            raise ConfigError(f"{rel(self.manifest_path)}: {where}{text!r} leaves the theme directory")
        # Resolved, so a symlink pointing out of the theme is caught too.
        base = self.dir.resolve()
        if not (base / pure).resolve().is_relative_to(base):
            raise ConfigError(f"{rel(self.manifest_path)}: {where}{text!r} resolves outside the theme directory")
        return self.dir / pure

    def stylesheets(self, target: str) -> list[Path]:
        """Stylesheets this theme loads for *target*, in declared cascade order."""
        declared = self.data["stylesheets"].get(target) or []
        return [self.path(p, key=f"stylesheets.{target}") for p in declared]

    def template(self, target: str) -> str:
        """Template name rendering *target*, relative to the theme's `templates/`.

        Relative to the Jinja loader's root rather than to the theme directory, so
        a name here reads the same way a ``{% extends %}`` inside a template does.
        """
        return str(self.data["templates"].get(target) or "")

    def template_path(self, target: str) -> Path:
        """Where :meth:`template`'s file lives on disk (existence not implied)."""
        return self.path(f"templates/{self.template(target)}", key=f"templates.{target}")

    def check_paths(self) -> None:
        """Resolve every path the manifest names, so a bad one fails at load.

        Called once when the manifest loads. Without it an escaping path is refused
        only when whichever caller needs that particular file reaches it — and for
        the EPUB stylesheets that is after the print HTML has already been written,
        which is a confusing place to learn the manifest was never usable.
        """
        for target in (PRINT, EPUB):
            self.stylesheets(target)
            self.template_path(target)
        if self.template(LANDING):
            self.template_path(LANDING)


def load_theme(theme_dir: Path) -> ThemeManifest:
    """Load a theme's `theme.yaml` manifest.

    A theme without a manifest still works: every key falls back to the value the
    core hardcoded before the manifest could declare it, so a manifest-less
    directory and a theme written against the older contract both render as before.
    """
    manifest = theme_dir / "theme.yaml"
    data: dict = {}
    if manifest.exists():
        loaded = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        if not isinstance(loaded, dict):
            raise ConfigError(f"{rel(manifest)} must be a mapping of theme settings, not a {type(loaded).__name__}")
        validate_theme_data(loaded, manifest)
        data = loaded
    loaded_manifest = ThemeManifest(dir=theme_dir, data=_normalize_theme(data), raw=data)
    loaded_manifest.check_paths()
    return loaded_manifest


def _is_path_reference(ref: str) -> bool:
    """True when *ref* points at a directory rather than naming an installed theme.

    Any separator makes it a path, so ``./mytheme`` and ``../shared/mytheme`` are
    paths even though they name one directory. ``Path("./mytheme")`` normalises
    to a single component, and treating component count as the test is what sent
    ``theme: ./mytheme`` looking inside site-packages.
    """
    return "/" in ref or os.sep in ref or ref.startswith("~") or Path(ref).is_absolute()


def theme_search_paths(name_or_path: str, root: Path | None = None) -> list[Path]:
    """Every directory a theme reference could name, in resolution order.

    A path is taken at its word — one candidate, no searching. A bare name is
    looked up the way Hugo and Zola look one up: beside the book first
    (``<root>/themes/<name>``, a theme vendored with the book), then among the
    themes shipped with ladle. So a book can carry its own ``themes/`` directory
    without either naming paths or colliding with the bundled set.

    *root* is the book's directory for a book-selected theme, the cwd for a
    standalone command like ``ladle theme lint``.
    """
    base = root or Path.cwd()
    if _is_path_reference(name_or_path):
        p = Path(name_or_path).expanduser()
        return [p if p.is_absolute() else base / p]
    return [base / "themes" / name_or_path, THEMES_DIR / name_or_path]


def resolve_theme_dir(name_or_path: str, root: Path | None = None) -> Path:
    """The directory a theme reference resolves to (see :func:`theme_search_paths`).

    Resolution only — a reference that matches nothing yields its last candidate,
    which is the conventional home for that reference and so the right thing to
    name in an error. Use :func:`require_theme_dir` where the theme has to exist.
    """
    candidates = theme_search_paths(name_or_path, root)
    return next((c for c in candidates if c.is_dir()), candidates[-1])


def require_theme_dir(name_or_path: str, root: Path | None = None) -> Path:
    """Like :func:`resolve_theme_dir`, but raise if no candidate is a directory.

    The message names every directory searched, because the failure this replaces
    reported a path in site-packages that the author never typed.
    """
    candidates = theme_search_paths(name_or_path, root)
    found = next((c for c in candidates if c.is_dir()), None)
    if found is None:
        raise ThemeNotFoundError(_theme_not_found_message(name_or_path, candidates))
    return found


def _theme_not_found_message(name_or_path: str, candidates: list[Path]) -> str:
    lines = [f"theme {name_or_path!r} not found. Searched:"]
    lines += [f"  {rel(c)}" for c in candidates]
    bundled = sorted(p.name for p in THEMES_DIR.iterdir() if p.is_dir()) if THEMES_DIR.is_dir() else []
    if bundled:
        lines.append(f"themes bundled with ladle: {', '.join(bundled)}")
    return "\n".join(lines)


def is_bundled_theme(theme_dir: Path) -> bool:
    """True for a theme shipped inside the package, false for the author's own.

    The two are held to different contracts: we can fix a bundled theme in the
    same commit that changes what the build passes it, so it is checked strictly.
    """
    return theme_dir.resolve().is_relative_to(THEMES_DIR.resolve())


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
    def theme_ref(self) -> str:
        """This book's `theme:` value, as written."""
        return self.data.get("theme", "default")

    @property
    def theme_dir(self) -> Path:
        """Design bundle (templates/css/fonts/patterns) this book renders with.

        Resolution only, so this stays safe to ask for: see
        :func:`theme_search_paths` for the order, and :meth:`require_theme_dir`
        for the same answer with a real error when the theme is not there.
        """
        return resolve_theme_dir(self.theme_ref, root=self.root)

    def require_theme_dir(self) -> Path:
        """This book's theme directory, or a ThemeNotFoundError naming the search."""
        return require_theme_dir(self.theme_ref, root=self.root)

    def theme_path(self, *parts: str) -> Path:
        return self.theme_dir.joinpath(*parts)

    def load_theme(self) -> ThemeManifest:
        """This book's theme manifest (see :func:`load_theme`)."""
        return load_theme(self.theme_dir)


def add_book_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--book",
        metavar="PATH",
        default=None,
        help="path to a book.yaml (default: ./book.yaml)",
    )


def resolve_book_path(cli_value: str | None = None) -> Path:
    value = cli_value or "book.yaml"
    return Path(value).resolve()


def _validate_against_schema(data: dict, path: Path, schema_path: Path) -> None:
    """Validate `data` against the JSON Schema at `schema_path`.

    Turns the first violation into a one-line ``<file>: <loc>: <why>`` `ConfigError`
    (a typo'd key, a wrong type, a missing required field), so config problems fail
    at load with a clear message instead of deeper in the build.
    """
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.validators.validator_for(schema)(schema)
    errors = sorted(validator.iter_errors(data), key=lambda e: list(e.path))
    if errors:
        e = errors[0]
        loc = "/".join(map(str, e.path))
        where = f"{loc}: " if loc else ""
        raise ConfigError(f"{rel(path)}: {where}{e.message}")


def validate_book_data(data: dict, path: Path) -> None:
    """Check a book.yaml `data` mapping against `book.schema.json` (strict surface).

    A typo'd key (`recipes` for `recipes_dir`), a wrong type (`sections` as a
    string), or a missing `title` becomes a friendly `ConfigError` at load.
    """
    _validate_against_schema(data, path, BOOK_SCHEMA_PATH)


def validate_theme_data(data: dict, path: Path) -> None:
    """Check a theme.yaml `data` mapping against `theme.schema.json` (strict surface).

    A typo'd key or a malformed `font_faces` entry becomes a friendly `ConfigError`
    at load, so a broken theme fails clearly instead of silently dropping tokens.
    """
    _validate_against_schema(data, path, THEME_SCHEMA_PATH)


def load_book_config(cli_value: str | None = None) -> BookConfig:
    path = resolve_book_path(cli_value)
    ui.detail(f"book config: {rel(path)}")  # -v diagnostic: which book we resolved
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise NoBookError(f"no book config found at {rel(path)}") from None
    try:
        data = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        detail = getattr(exc, "problem", None) or "could not parse"
        mark = getattr(exc, "problem_mark", None)
        where = f" (line {mark.line + 1})" if mark is not None else ""
        raise ConfigError(f"invalid YAML in {rel(path)}: {detail}{where}") from None
    if not isinstance(data, dict):
        raise ConfigError(f"{rel(path)} must be a mapping of book settings, not a {type(data).__name__}")
    validate_book_data(data, path)
    return BookConfig(path=path, data=data)
