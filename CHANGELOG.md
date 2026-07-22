# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- `ladle theme lint <theme>` — the featured-gallery gate: checks that a theme's
  `theme.yaml` validates against the schema, that its templates load in the Jinja
  sandbox, and that every embedded font family names a present file with a
  documented, redistribution-friendly license. Exits non-zero on failure (CI-ready).
- `ladle theme preview <theme>` — renders a theme against the bundled canonical
  sample book into `build/preview/<theme>/`: a PDF plus, when poppler is present, a
  `cover.png` and `contact-sheet.png` for eyeballing or a gallery card. Pass
  `--book` to preview against your own book. Adds a small sample book to the package.
- `ladle validate --strict` — fails the run when a recipe body contains content
  the parser cannot place, for CI and for anyone who wants the guarantee.

### Changed

- Theme templates now render in a `jinja2.sandbox.SandboxedEnvironment`, so an
  untrusted community theme is treated as data, never code; a template that trips
  the sandbox surfaces as a friendly error naming the file.
- `build` and `validate` now report recipe body content that no parser rule
  claims, instead of dropping it silently. The parsers only understand `- item`
  and `### group` under `## INGREDIENTS`, numbered `1.` steps under
  `## DIRECTIONS`, and free prose under `## NOTES`; anything else — a step
  wrapped onto a second line, an unbulleted ingredient, a section under a
  heading ladle does not read — used to vanish with no warning, and a truncated
  step still looks like a complete sentence on the page. Diagnostics are
  `file:line: message`; `build` caps them and points at `validate` for the full
  list.
- A recipe whose front matter opens with `---` but never closes it now fails
  with a message naming the file, instead of a raw `ValueError` traceback.
- A `##` heading repeated within one recipe now accumulates its blocks; the
  earlier block used to be discarded.
- `validate`'s contact sheet is ~16x faster (a 224-page book went 147s -> ~9s in
  measurement): it rasterizes small glancing-resolution thumbnails instead of
  reading-resolution pages, across concurrent page-range workers.

### Fixed

- `validate`'s contact sheet for a long book (~145+ pages) used to be a single
  image taller than the ~16384px canvas dimension many viewers can open — it now
  paginates into `contact-sheet.png`, `contact-sheet-02.png`, … so every sheet
  stays openable.

- The bundled sample book had a direction step wrapped onto a second line, so
  `ladle theme preview` rendered it truncated mid-clause.

## [0.2.0] - 2026-07-12

This release sharpens `ladle` around its one job — building a book. The CLI is
reorganized behind a command registry with consistent global flags, and the
surface is narrowed from nine commands to four: `new`, `build`, `validate`,
`doctor`.

### Added

- Global flags, via a shared console and central dispatch: `-v`/`--verbose` and
  `-q`/`--quiet` for verbosity, `--color`/`--no-color` to force color
  (auto-detection honors a TTY, `NO_COLOR`, and `TERM=dumb`), and `--no-input`
  to run without prompts. All diagnostics go to stderr; stdout stays clean for
  piping.
- `-V`/`--version` reports the installed version, single-sourced from the
  package metadata so it can't drift from `pyproject.toml`.
- Per-command `--help`, each leading with runnable examples and linking the repo.
- `doctor --install` offers to install missing system dependencies for you
  (Homebrew/apt + `pip`) — it prints the exact commands and asks before running
  anything — instead of only reporting them.
- Granular exit codes and next-step error hints, so failures are scriptable and
  self-explanatory.
- `build` warns on schema-invalid recipes rather than failing silently.
- Community-health files: `SECURITY.md`, `CHANGELOG.md`, `NOTICE`, issue and
  pull-request templates, and a Dependabot configuration.
- A `pytest` unit-test suite covering config/path resolution and the
  dependency-free markdown/recipe parsing, plus `test`/`dev` optional-dependency
  groups and `ruff` configuration.
- CI runs `ruff` lint and the unit tests across Python 3.11–3.13, gating
  releases on both alongside the example-book build.

### Changed

- `ladle new` redesigned: takes a positional `<name>` (was `--name`), scaffolds
  `./<name>/` (was `books/<name>/`) populated with a first-run recipe so
  `cd <name> && ladle build` works immediately, keeps the name verbatim
  (rejecting only path-unsafe input), and guards an existing directory behind
  `--force`.
- The top-level help is generated from a command registry into
  USAGE / COMMANDS / GLOBAL FLAGS / EXAMPLES sections with consistent headings.
- Book selection simplified to `--book PATH` or `./book.yaml`.
- Replaced the example cookbook's recipes (previously attributed to real chefs
  and published sources) with original, neutrally-credited sample recipes, and
  renamed the example book to **The Ladle Kitchen** (was "The Community
  Cookbook"); its directory moved to `examples/the-ladle-kitchen/`.
- Overhauled the README for the public launch — status badges, a hero image, a
  terminal demo, tightened copy and package metadata — and adopted `ruff format`
  with local tooling config.

### Removed

- The `html`, `pdf`, and `epub` commands — building is now a single
  `ladle build` that runs the HTML → PDF → EPUB pipeline internally (these were
  never independently useful; `pdf`/`epub` require `build`'s HTML first).
- The `illustrations` and `assets` commands — placeholder illustrations and
  asset resolution are handled as part of scaffolding and `build`.
- The `$BOOK_CONFIG` environment override for locating a book; use `--book` or
  `./book.yaml`.
- CI no longer publishes a rolling "latest" book release or the example book to
  GitHub Pages — this repository ships the `ladle` tool; book editions are cut
  from their own repositories.

### Fixed

- Malformed or incomplete `book.yaml` files now produce friendly, actionable
  errors instead of a raw traceback.

### Security

- Hardened CI: pinned all GitHub Actions to commit SHAs, verified the SHA-256 of
  the downloaded pandoc and epubcheck releases, and scoped workflow token
  permissions to least privilege.

## [0.1.0] - 2026-07-05

### Added

- Initial public release: build an art-directed PDF (WeasyPrint) and an
  epubcheck-clean EPUB (pandoc) from a folder of markdown recipes driven by a
  single `book.yaml`.
- `ladle` CLI: `new`, `build`, `html`, `pdf`, `epub`, `illustrations`,
  `assets`, `validate`, `doctor`.
- Swappable themes (bundled `default` theme) with per-book palette/font/label
  overrides.
- Deterministic SVG placeholder illustrations, with automatic preference for a
  raster sibling when real artwork is dropped in.

[Unreleased]: https://github.com/dimitri-kandassamy/ladle/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/dimitri-kandassamy/ladle/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/dimitri-kandassamy/ladle/releases/tag/v0.1.0
