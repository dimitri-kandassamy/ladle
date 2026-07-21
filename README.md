# ladle

[![GitHub](https://img.shields.io/badge/GitHub-dimitri--kandassamy%2Fladle-181717?logo=github)](https://github.com/dimitri-kandassamy/ladle)
[![PyPI version](https://img.shields.io/pypi/v/ladlebook.svg)](https://pypi.org/project/ladlebook/)
[![Python versions](https://img.shields.io/pypi/pyversions/ladlebook.svg)](https://pypi.org/project/ladlebook/)
[![License](https://img.shields.io/github/license/dimitri-kandassamy/ladle)](https://github.com/dimitri-kandassamy/ladle/blob/main/LICENSE)
[![CI](https://github.com/dimitri-kandassamy/ladle/actions/workflows/build.yml/badge.svg)](https://github.com/dimitri-kandassamy/ladle/actions/workflows/build.yml)

**Turn a folder of markdown recipes into a beautifully typeset cookbook — a
print-ready PDF and a validated, reflowable EPUB — from a single `ladle build`.**

`ladle` is a command-line tool that builds art-directed cookbooks from plain
markdown and a single `book.yaml`. The design — fonts, palette, layout — lives
in a swappable **theme**, fully decoupled from your words, so the same recipes
can be restyled without touching a line of content. It's plain Python with no
browser and no Node, built for home cooks, communities, and small publishers who
would rather keep their recipes in version-controlled plain text than locked
inside a proprietary app.

![A spread from the example cookbook, built by ladle](https://raw.githubusercontent.com/dimitri-kandassamy/ladle/main/docs/assets/hero.png)

_The example cookbook — a print-ready PDF from plain markdown._

<!-- markdownlint-disable-next-line MD033 -- inline <img> needed to size the demo GIF -->
<img alt="Building a cookbook from the terminal" src="https://raw.githubusercontent.com/dimitri-kandassamy/ladle/main/docs/assets/demo.gif" width="600" />

_One folder of markdown → a validated PDF + EPUB, from a single `ladle build`._

## Installation

`ladle` needs Python 3.11+ and a few small command-line tools (one runtime — no
browser, no Node).

### 1. Install the package

```sh
pip install ladlebook      # the PyPI package; the command it installs is `ladle`
```

### 2. Install the system tools

[WeasyPrint](https://weasyprint.org) (the PDF engine) needs the Pango/cairo
libraries; pandoc builds the EPUB; poppler powers the PDF checks and EPUB cover.

- **macOS:** `brew install pango poppler pandoc`
- **Debian/Ubuntu:** `sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 poppler-utils pandoc`

| Tool    | Version    | Used for                                               |
| ------- | ---------- | ------------------------------------------------------ |
| Python  | 3.11+      | the tool itself                                        |
| pandoc  | 3.x        | EPUB generation                                        |
| poppler | any recent | `pdfinfo` + `pdftoppm` (PDF checks, EPUB cover)        |
| Java    | 17+        | optional — only to run `epubcheck` in `ladle validate` |

Then confirm everything is wired up. `ladle doctor` reports anything missing
with per-OS install hints — or let `ladle doctor --install` run the right
package-manager commands for you (Homebrew/apt + `pip`). It prints the exact
commands and asks before running anything:

```sh
ladle doctor            # check the toolchain
ladle doctor --install  # …and offer to install whatever's missing
```

## Usage

Scaffold a book, add recipes, and build:

```sh
ladle new mybook                 # scaffold ./mybook/ (or `ladle new` -> ./book/)
cd mybook
# …add your recipes under recipes/…
ladle build                      # -> build/cookbook.pdf and build/cookbook.epub
ladle validate                   # schema + body + PDF structure + epubcheck + contact sheet
open build/contact-sheet.png     # a thumbnail grid of every page
```

Book-scoped commands take `--book PATH` (default: `./book.yaml`),
so you can keep several books side by side and build any of them.

### A recipe is just markdown

```markdown
---
title: Carrot Cake
category: Desserts # Savory | Desserts | Beverages
servings: "6 people" # optional
credits: "The Ladle Kitchen" # optional — a person, a book, or a URL
illustration: assets/illustrations/recipes/carrot-cake.svg
# optional: page, story, author:{name,org}, headshot, attribution, tags, license, draft
---

## INGREDIENTS

### Cake # optional group headings

- 2 large eggs
- 200g sugar

## DIRECTIONS

1. Pre-heat the oven to 180°C.
2. …

## NOTES # optional

- Keeps for several days.
```

A recipe with a non-empty `story:` gets a full story page (with an optional
`headshot`); without one it gets a compact opener. Every recipe is validated
against [`recipe.schema.json`](https://github.com/dimitri-kandassamy/ladle/blob/main/src/ladle/schema/recipe.schema.json).

The body has a contract too, and only these shapes are rendered:

| Under            | ladle reads                                              |
| ---------------- | -------------------------------------------------------- |
| `## INGREDIENTS` | `- item` lines, optionally split by `### group` headings |
| `## DIRECTIONS`  | numbered `1.` steps, one per line                        |
| `## NOTES`       | free prose                                               |

The headings are matched literally, so they stay in English even in a
translated book (`labels:` controls what is _printed_). Anything else — a step
wrapped onto a second line, an ingredient without its `-`, a section under
another heading — is content ladle cannot place. It is reported by `build` and
by `ladle validate`, as `file:line`, rather than silently dropped; use
`ladle validate --strict` to make it fail the run.

`illustration:` is optional. A recipe without one simply renders no hero image.

### A book is a folder

```text
mybook/
  book.yaml            # title, language, theme, palette/font overrides, section order
  recipes/*.md         # one recipe per file (front matter + body)
  content/introduction.md
  assets/illustrations/recipes/*   # generated per-recipe art (real art drops in as PNG)
```

`book.yaml` needs only a `title` to build — everything else (palette, fonts,
labels) falls back to the theme's defaults. Section headings and all UI chrome
("Yields", "Contents", section names) are localizable per book via a `labels:`
block. See the reference book in
[`examples/the-ladle-kitchen/`](https://github.com/dimitri-kandassamy/ladle/tree/main/examples/the-ladle-kitchen)
for a complete, working template.

### Commands

| Command                       | Does                                                           |
| ----------------------------- | -------------------------------------------------------------- |
| `ladle new [X]`               | scaffold a new book in `./X/` (default `./book/`)              |
| `ladle build`                 | build the PDF + EPUB from your recipes                         |
| `ladle validate`              | recipe schema + body, PDF trim + page count, epubcheck, sheet  |
| `ladle doctor`                | check pandoc/poppler/WeasyPrint/Java are installed             |

## Build from source

```sh
git clone https://github.com/dimitri-kandassamy/ladle && cd ladle
pip install -e .                 # or: pip install -r requirements.txt
make all                         # builds the example book (examples/the-ladle-kitchen)
make validate
```

`make` drives the package straight from `src/` (no install needed);
`make all BOOK=path/to/book.yaml` builds any book, and the `Makefile` targets
mirror the CLI commands. CI builds and validates the example book plus a
torture-test fixture on every push.

## Themes

The look is a **theme**: a self-contained bundle of `theme.yaml` (palette, fonts,
font files) plus `templates/`, `css/`, `fonts/`, and `illustrations/patterns/`.
The tool ships one theme, `default`. To restyle, override tokens in `book.yaml`,
or fork the theme and point `theme:` at your own directory. See
[docs/THEMING.md](https://github.com/dimitri-kandassamy/ladle/blob/main/docs/THEMING.md).

## Illustrations

Recipe artwork lives with your book, not in the tool. Point a recipe's
`illustration:` front matter at a file under `assets/illustrations/recipes/`
(SVG or a raster — PNG/WebP/JPEG), and drop the file in. If both an SVG and a
raster sibling exist (e.g. `carrot-cake.svg` and `carrot-cake.png`), the build
prefers the raster automatically — so you can start with a simple placeholder and
swap in real art later with no front-matter change.

## Contributing

Contributions are welcome — code, themes, docs, or a recipe for the example book.
Start with [CONTRIBUTING.md](https://github.com/dimitri-kandassamy/ladle/blob/main/CONTRIBUTING.md)
for the dev setup and repository layout, and see
[DESIGN.md](https://github.com/dimitri-kandassamy/ladle/blob/main/DESIGN.md) for
the parse → render → build pipeline and design rationale. By participating you
agree to the
[Code of Conduct](https://github.com/dimitri-kandassamy/ladle/blob/main/CODE_OF_CONDUCT.md).
Found a security issue? See our
[Security Policy](https://github.com/dimitri-kandassamy/ladle/blob/main/SECURITY.md).

## License

- **Code** (the tool, themes, CSS, templates): Apache-2.0 — see [`LICENSE`](https://github.com/dimitri-kandassamy/ladle/blob/main/LICENSE).
- **Content** (the example book's sample recipes and illustrations): CC BY-SA 4.0
  — see [`LICENSE-CONTENT`](https://github.com/dimitri-kandassamy/ladle/blob/main/LICENSE-CONTENT), unless a recipe's `license:` says otherwise.

## Credits & thanks

- **Inspiration** — the
  [Cloud Native Community Cookbook](https://github.com/cncf/cloud-native-community-cookbook),
  originated by [Equinix Metal](https://www.equinix.com).
- **Type** (default theme) — [Playfair Display](https://github.com/clauseggers/Playfair-Display)
  and [Bitter](https://github.com/solmatas/BitterPro), both under the SIL Open Font License.
- **Tooling** — [WeasyPrint](https://weasyprint.org) (PDF),
  [pandoc](https://pandoc.org) (EPUB), [poppler](https://poppler.freedesktop.org),
  [epubcheck](https://www.w3.org/publishing/epubcheck/), plus
  [Jinja](https://jinja.palletsprojects.com), [PyYAML](https://pyyaml.org),
  [jsonschema](https://github.com/python-jsonschema/jsonschema), and
  [Pillow](https://python-pillow.org).
