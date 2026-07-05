# ladle — Spec & Plan

> A dependency-light CLI that turns a folder of markdown recipes into an
> art-directed **PDF** and a validated **EPUB**, with swappable themes — plus an
> optional, local recipe **ingestion** path that acquires recipes from the web,
> PDFs, and EPUBs you own.
>
> **Status:** the **builder** (markdown → PDF + EPUB) is implemented and shipped
> as `ladle` v0.1. This document is both the description of that tool and the
> plan for **Phase 2** (recipe ingestion + CLI polish). Status markers below:
> ✅ implemented · 🔜 Phase 2 (planned) · 🧊 deferred.

---

## 1. Context & goal

`ladle` builds a cookbook — an art-directed **PDF** (print) and a reflowable,
validated **EPUB** — from plain-markdown recipes plus one `book.yaml` and a
swappable theme. Design is decoupled from content, so the same recipes render
under any theme, and any book can bring its own.

The tool is one half of a two-stage pipeline:

- **Back half — publishing (✅ done).** clean markdown → beautiful book. This is
  ladle's core and its differentiator (the print PDF is the hard part).
- **Front half — acquisition (🔜 Phase 2).** source (blog/PDF/owned EPUB) →
  clean per-recipe markdown. This is the drudgery-killer for a growing personal
  cookbook, and the main thing ladle doesn't do yet.

The two halves meet at **`recipes/<slug>.md`** — the committed source of truth
and the stable contract between ingestion and the build.

### Decisions locked (this revision)

- **Keep ladle as the deterministic, dependency-light builder.** Do *not* rewrite
  it to be EPUB-only, TOML-configured, pydantic-schema'd, or Typer-based — those
  are incidental style choices that would cost the PDF and working code for
  negligible user value (see §11).
- **Output stays PDF + EPUB.** EPUB is epubcheck-validated; PDF is the
  art-directed print artifact.
- **Add acquisition additively, cheapest-value-first:** a deterministic web
  (schema.org/Recipe JSON-LD) extractor **with no LLM** lands first; a **local**
  Ollama fallback follows behind an optional extra (`pip install ladle[ingest]`);
  PDF/EPUB source extractors come later.
- **CI stays LLM-free and deterministic** — it builds only from committed
  markdown and never runs Ollama or the network extractors. Ingestion is local.
- **Config is `book.yaml` (YAML).** Recipe schema is JSON Schema. CLI is argparse.
  We adopt clig.dev *conventions* (§3) without adopting Typer.
- **Themes are hand-authored bundles** (a `theme.yaml` manifest + templates/css/
  fonts/patterns). Distilling a theme from an EPUB (`extract-template`) is 🧊.
- **Photos / OCR / vision are out of scope** for now (blogs/PDFs/EPUBs first).

**Tooling.** Runtime: Python 3.11+, pandoc, poppler (`pdfinfo`/`pdftoppm`),
WeasyPrint's Pango/cairo libs; Java is optional (only for `epubcheck`).
Phase-2 ingestion adds (as an optional extra): an HTML fetch/parse stack and a
local Ollama daemon + model. `ladle doctor` checks the required set.

---

## 2. Architecture

One canonical **Recipe** shape; sources only *extract*; one renderer writes
markdown; one builder turns markdown → PDF + EPUB.

```text
FRONT HALF (🔜 Phase 2, local only)
source (url / pdf / epub / text)
  └─ extract.py    → RawExtraction (structured if JSON-LD present, else raw text)
       └─ normalize.py → Recipe   (deterministic map when JSON-LD; Ollama otherwise)
            └─ render → recipes/<slug>.md      ← SOURCE OF TRUTH, committed
                                   │
BACK HALF (✅ implemented)          │
a book (book.yaml + recipes/*.md + content/) + a theme
  └─ ladle html  (build_html.py, Jinja)
       ├─ build/cookbook.html → ladle pdf   (make_pdf.py, WeasyPrint) → build/cookbook.pdf
       └─ build/epub.html     → ladle epub  (make_epub.py, pandoc)    → build/cookbook.epub → epubcheck
```

CI rebuilds PDF + EPUB from committed markdown on every push; ingestion (the only
LLM/network step) is strictly local.

### Repository layout — the tool (this repo)

```text
ladle/
├── src/ladle/                  # the package (command: `ladle`)
│   ├── cli.py  __main__.py      # subcommand dispatch
│   ├── config.py                # book.yaml + path/theme resolution
│   ├── build_html.py            # recipes + book + theme → print/epub HTML (Jinja)
│   ├── make_pdf.py              # print HTML → PDF (WeasyPrint)
│   ├── make_epub.py             # epub HTML → EPUB (pandoc) + metadata/fonts
│   ├── gen_illustrations.py     # per-recipe SVG placeholders + theme patterns
│   ├── bake_assets.py           # bake a theme's raster paper/patterns (palette-driven)
│   ├── validate.py              # schema + PDF structure + epubcheck + contact sheet
│   ├── doctor.py                # preflight for pandoc/poppler/WeasyPrint/Java
│   ├── new_book.py              # scaffold a new book under books/<name>/
│   ├── schema/recipe.schema.json
│   └── themes/default/          # the built-in theme (manifest + templates/css/fonts/patterns)
│   ├── extract.py   normalize.py   ollama.py   # 🔜 Phase 2 (front half)
├── examples/community-cookbook/ # reference book that ships with the tool
├── tests/fixtures/torture-book/ # CI edge-case fixture
├── Makefile                     # thin wrapper over the CLI (dev)
└── .github/workflows/build.yml  # lint · build+validate · publish to PyPI on tags
```

### A user's book (built by `ladle new`, or a repo that `pip install ladle`s)

```text
my-cookbook/
├── book.yaml                    # THE config (§5)
├── recipes/*.md                 # source of truth, one recipe per file
├── content/introduction.md
├── assets/illustrations/recipes/  # generated per-recipe art (raster art drops in)
├── themes/<name>/               # optional book-local theme (else a bundled one)
└── build/                       # generated PDF/EPUB/contact-sheet/index.html (gitignored)
```

### Package modules

| Module | Responsibility | Status |
| --- | --- | --- |
| `config.py` | Load `book.yaml` → paths; resolve theme (bundled name or path); build dir; epubcheck jar. | ✅ |
| `build_html.py` | Parse `recipes/*.md` + book + theme → `cookbook.html` (print) & `epub.html`. | ✅ |
| `make_pdf.py` | `cookbook.html` → `cookbook.pdf` (WeasyPrint, CSS Paged Media). | ✅ |
| `make_epub.py` | `epub.html` → `cookbook.epub` (pandoc epub3, theme fonts/css, cover, metadata). | ✅ |
| `gen_illustrations.py` | On-brand SVG placeholders per recipe + theme pattern art. | ✅ |
| `bake_assets.py` | Bake a theme's raster paper grain + patterns from its palette. | ✅ |
| `validate.py` | Recipe JSON Schema + PDF trim/page-count diagnostic + epubcheck + contact sheet. | ✅ |
| `doctor.py` | Preflight: pandoc / poppler / WeasyPrint / Java, with per-OS hints. | ✅ |
| `new_book.py` | Scaffold `books/<name>/` (book.yaml + content + a draft recipe). | ✅ |
| `cli.py` | argparse dispatch; global flags; output/exit-code conventions (§3, §6). | ✅ (conventions 🔜) |
| `schema.py` | Shared recipe field definitions reused by build/lint/ingest. | 🔜 (today: JSON Schema file) |
| `extract.py` | Source detection + extractors: web JSON-LD → readable-text; then pdf, epub. | 🔜 |
| `normalize.py` | `RawExtraction → Recipe`: deterministic map (JSON-LD) else Ollama. | 🔜 |
| `ollama.py` | Thin local Ollama REST client (`/api/chat`, `format:<json schema>`). | 🔜 (optional extra) |

---

## 3. CLI design principles (clig.dev)

Baked into `cli.py` once; adopted incrementally (argparse, **not** Typer).

- **Human-first, machine-ready.** Primary output → **stdout**; logs/progress/
  errors → **stderr**. A brief success line is always printed ("Wrote
  recipes/x.md", "Wrote build/cookbook.pdf"). ✅ (success lines) / 🔜 (strict stream split)
- **Every flag has a long form**; short forms only for common ones; order-free. Book-scoped commands take `--book PATH`. ✅
- **`--help` everywhere**, including subcommands; lead help with examples; footer links the repo. 🔜
- **`--json` / `--plain`** for data commands (`list`, `theme list`, `lint`, `validate`) — the stable scripting contract; human output may change. 🔜
- **Color & TTY.** Color/spinners only on a TTY; disabled when piped, `TERM=dumb`, `NO_COLOR`, or `--no-color`. 🔜
- **Interactivity gated on TTY.** Prompts only if stdin is a TTY; `--no-input` uses defaults / fails fast; Ctrl-C exits cleanly. 🔜
- **`-` means stdin/stdout** where a file is expected (`ingest -`, `build -o -`). 🔜
- **Destructive actions confirm, scaled to severity.** `theme use` = none; overwriting a recipe/theme = `y/N` or `--force`; `--dry-run` previews `ingest`/`build`. ✅ (`--force` on `new`) / 🔜 (rest)
- **Errors rewritten for humans**, key info last, **suggest the next command**
  ("No book.yaml found — run `ladle new` or pass `--book`."). Tracebacks only with `--debug`. 🔜
- **Validate early, fail fast**; sensible network timeouts; spinner for fetches/model calls/builds. 🔜
- **Idempotent & recoverable.** Re-running `build`/`ingest` is safe; verb-based command names, no catch-all default. ✅

---

## 4. Command reference

Global form: `ladle [GLOBAL FLAGS] <command> [ARGS] [FLAGS]`

### Global flags

| Flag | Meaning | Status |
| --- | --- | --- |
| `-h, --help` | Show help. | ✅ |
| `--version` | Print version and exit. | ✅ |
| `-v, --verbose` / `-q, --quiet` | More / less detail on stderr. | 🔜 |
| `--debug` | Developer output + full tracebacks. | 🔜 |
| `--json` / `--plain` | Machine-readable / tab-separated output where data is produced. | 🔜 |
| `--no-color` | Disable color (also `NO_COLOR`, non-TTY, `TERM=dumb`). | 🔜 |
| `--no-input` | Never prompt; use defaults or fail. | 🔜 |
| `-C, --chdir <dir>` | Run as if started in `<dir>`. | 🔜 |
| `--book <path>` | Book config to operate on (default `$BOOK_CONFIG` or `./book.yaml`). | ✅ |

### Implemented commands (✅)

- **`ladle build`** — `html` → `pdf` → `epub`. Flags (planned): `--pdf`/`--epub`
  only, `-o/--output`, `--drafts`, `--no-validate`, `--watch` 🔜.
- **`ladle html` / `pdf` / `epub`** — run a single build stage.
- **`ladle new [--name X]`** — scaffold a new book under `books/X/`
  (`--title`, `--subtitle`, `--language`, `--palette-*`, `--force`). *The `hugo new site` analog.*
- **`ladle illustrations [--force]`** — (re)generate SVG placeholder art.
- **`ladle assets [--theme DIR]`** — re-bake a theme's raster paper/patterns.
- **`ladle validate`** — recipe schema + PDF trim/page count + epubcheck (or a
  structural fallback without Java) + contact sheet. Non-zero exit on failure.
- **`ladle doctor`** — preflight tool check with per-OS install hints.

### Planned commands (🔜 Phase 2)

- **`ladle ingest <SOURCE>`** — acquire a recipe. `SOURCE` = URL, `.pdf`/`.epub`/
  `.txt` path, or `-` (stdin). Extract (JSON-LD → readable-text / pdftotext /
  epub text) → normalize (deterministic, or Ollama with `[ingest]`) → preview →
  write `recipes/<slug>.md`. Flags: `--category`, `--chapter`, `--model`,
  `--dry-run`, `--force`, `--no-archive`. Preview/confirm only on a TTY.
- **`ladle list`** — list recipes (`--json`/`--plain`, `--category`, `--tag`, `--sort`).
- **`ladle theme <list|show|use>`** — manage themes; `theme use <slug>` writes
  `theme:` into `book.yaml`. (Distilling a theme from an EPUB is 🧊.)
- **`ladle lint`** — validate every recipe's front matter against the schema
  (`--json`/`--plain`, `--fix` for trivial safe fixes). Split out of `validate`.

---

## 5. Configuration — `book.yaml`

Single per-book config (YAML). Loaded by `config.py`.

```yaml
title: Family Recipes
subtitle: Stories & food from people who love to cook
language: en                 # ISO 639-1
volume: "1.0"
rights: "© 2026 D. K."       # optional — omitted safely (no empty dc:rights in the EPUB)
producer: D. K.
content_license: CC-BY-SA-4.0
repo_url: https://github.com/you/your-cookbook

theme: default               # bundled theme name, or a path to a book-local theme

sections: [Savory, Desserts, Beverages]   # TOC parts; recipes grouped by `category`
order: []                    # optional explicit ordering by slug

recipes_dir: recipes         # defaults shown; resolved relative to this book.yaml
illustrations_dir: assets/illustrations/recipes
introduction: content/introduction.md

# palette / fonts / labels are OPTIONAL — they fall back to the theme's defaults,
# and override per key when present. `labels:` localizes UI chrome + section names.

# [ingest] (🔜 Phase 2, local only — never read in CI):
# ingest:
#   model: gemma3:latest
#   host: http://localhost:11434
#   archive_sources: true    # keep originals under sources/
```

**Precedence (highest→lowest):** command flags → environment
(`BOOK_CONFIG`, `LADLE_BUILD`, `EPUBCHECK_JAR`; 🔜 `LADLE_MODEL`, `LADLE_HOST`,
`NO_COLOR`, `EDITOR`, `PAGER`) → `book.yaml` → theme defaults → built-in defaults.
Book selection: `--book` → `$BOOK_CONFIG` → `./book.yaml`. (🔜 Hugo-style
walk-up to find the nearest `book.yaml` from a subdirectory.)

---

## 6. Exit codes

| Code | Meaning | Status |
| --- | --- | --- |
| `0` | Success. | ✅ |
| `1` | General runtime error (human-readable message on stderr). | ✅ |
| `2` | Usage error (bad flags/args / unknown command). | ✅ |
| `3` | No book config found — suggests `ladle new` / `--book`. | 🔜 |
| `4` | Validation failed (`validate`/`lint`/epubcheck errors). | 🔜 (today: non-zero via `1`) |
| `5` | Source/extraction error (fetch failed, unreadable PDF/EPUB, Ollama down). | 🔜 |

---

## 7. CI

**Tool repo** (`.github/workflows/build.yml`, ✅): lint markdown →
`pip install -e .` → build + validate the **example book** and the
**torture-test fixture** → on a `v*` tag, publish `ladle` to **PyPI** (Trusted
Publishing). Deterministic and **LLM-free** — never runs ingestion.

**A book repo** (e.g. the flagship cookbook that `pip install ladle`s): builds
PDF + EPUB on push, publishes a rolling `latest` release + versioned editions on
`v*` tags, and (opt-in) deploys the `build/` download page + artifacts to
**GitHub Pages**. Also consumes only committed markdown.

---

## 8. Recipe markdown schema

YAML front matter + a markdown body. Validated by `recipe.schema.json` (JSON
Schema). Required: **`title`**, **`category`**. Body sections are matched
case-insensitively and are localizable via `book.yaml`'s `labels:`.

```markdown
---
title: Classic Margherita Pizza
slug: classic-margherita-pizza       # optional (defaults from filename)
category: Savory                     # one of book.yaml's `sections`
servings: "2"                        # optional
credits: "A. Cook"                   # optional — named source
page: 42                             # optional — source page (archival books)
illustration: assets/illustrations/recipes/classic-margherita-pizza.svg
tags: [italian, vegetarian]          # optional
draft: false                         # excluded from the build unless --drafts
# optional: story, author:{name,org}, headshot, attribution, license
# 🔜 Phase 2 (additive, for ingest provenance/parity):
#   prep_time: "20 min"
#   cook_time: "12 min"
#   source: { type: web, url: "https://…", author: "…", retrieved: 2026-06-02 }
---

## INGREDIENTS
### Dough                             # optional group headings
- 500 g 00 flour

## DIRECTIONS
1. …

## NOTES                              # optional
…
```

**Schema unification (🔜, the front/back contract).** Before the first extractor
lands, extend the schema **additively** with `prep_time`, `cook_time`, and a
`source` provenance object, so whatever `ingest` produces, `build` can render.
Existing fields (`illustration`, `story`, `credits`, `page`, `author`, …) stay.

---

## 9. Themes

A theme is a self-contained bundle selected by `book.yaml`'s `theme:` (bundled
name or path). The tool ships one built-in theme, `default`.

```text
themes/<name>/
  theme.yaml            # name, description, palette, fonts, font_faces
  templates/{print,epub}.html.j2
  css/{common,print,epub}.css
  fonts/*.ttf
  illustrations/patterns/*   # cover/endpaper/back svg + baked paper rasters
```

Palette/fonts in `theme.yaml` are defaults a `book.yaml` overrides per key. See
`docs/THEMING.md`. Planned: **`ladle theme use`** to switch (🔜). Distilling a
theme's CSS/fonts from an owned EPUB (`extract-template`) is **deferred** (🧊) —
CSS reproduction across pandoc's structure is approximate and font licenses vary.

---

## 10. Implementation order (Phase 2)

Cheapest-value-first; each step keeps the builder green and CI LLM-free.

1. **Schema extension (§8).** Add `prep_time`/`cook_time`/`source` to the JSON
   Schema (additive); thread through `build_html` where surfaced. *The contract.*
2. **Web JSON-LD `ingest` (no LLM).** `extract.py` (schema.org/Recipe) +
   `render` → `ladle ingest <url>` writes a real `recipes/*.md`. Deterministic,
   CI-safe, big payoff. *The spine of the front half.*
3. **CLI conventions + cheap commands.** Standardize stdout/stderr, exit codes
   (§6), `--json`/`--plain`, `--no-color`, `--no-input`, `-C`; add `ladle list`,
   `ladle theme list/show/use`, `ladle lint`. Pure upside, no new heavy deps.
4. **Readable-text fallback + local Ollama.** `normalize.py` + `ollama.py` behind
   the optional `ladle[ingest]` extra; non-JSON-LD pages → model → Recipe.
   Local-only; never in CI.
5. **PDF & EPUB source extractors.** `pdftotext -layout` and epub XHTML text →
   the same normalize path. `--chapter` selector for EPUBs.
6. **Docs.** README "acquire → review → commit → push → auto-build" loop;
   `docs/INGEST.md`; update `ladle doctor` to check the ingest toolchain.

---

## 11. Non-goals / rejected directions

- **EPUB-only.** Rejected — PDF (art-directed print) is ladle's differentiator.
- **Migrating YAML→TOML, jsonschema→pydantic, argparse→Typer** *for their own
  sake.* Rejected — churn that rewrites working code for negligible user value.
  We adopt clig.dev *conventions*, not the frameworks. Revisit only on a concrete need.
- **`extract-template`** (distill a theme from an EPUB). Deferred (🧊) — approximate
  and license-fraught; hand-authored themes cover the need.
- **Photos / OCR / vision ingestion.** Out of scope now; a later multimodal
  Ollama model or a tesseract path (with imagemagick) could add it.
- **Running the LLM/network in CI.** Never — CI consumes only committed markdown.

---

## 12. Verification

- **Builder (✅, keep green):** `ladle build` + `ladle validate` on the example
  (28-page PDF, epubcheck clean) and the torture fixture; a minimal book (title
  only) builds and validates from theme defaults.
- **Schema (🔜):** additive fields validate; existing recipes still pass.
- **Ingest (🔜):** JSON-LD parser against a saved blog-HTML fixture → `recipes/*.md`
  that `validate` accepts and `build` includes; `normalize` mapping with a mocked
  Ollama; `ingest -` reads stdin; `--dry-run` writes nothing.
- **CLI conventions (🔜):** `--help` on every command; `--json` parses; piped
  output drops color; `--no-input` never prompts; bad usage → 2; missing book → 3.
- **CI:** push a branch → build + epubcheck pass; PyPI publish on a `v*` tag;
  ingestion never invoked.

---

## 13. Caveats / open questions

- **Ingest dependency surface.** Keep the core builder dependency-light: the
  HTML/LLM stack lives in the `ladle[ingest]` extra so `pip install ladle` stays
  lean and CI never pulls it. If it still feels heavy inside the repo, the
  fallback is a separate companion tool that writes the same `recipes/*.md`.
- **Ollama model.** Local, text-only; name/host from config/env; clear error if
  the daemon is down. Deterministic JSON-LD path runs first, so many blogs need
  no model at all.
- **Copyright.** Ingest owned/permissible sources; store provenance in `source:`.
  Themes: reuse *styling* for personal use, but ship your own cover and prefer
  the built-in themes; confirm font licenses before embedding/redistributing.
- **To resolve later:** Hugo-style `book.yaml` walk-up; whether `sources/`
  archives use git-lfs; a `ladle build --watch` / preview server.
