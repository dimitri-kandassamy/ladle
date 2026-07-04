# ladle

**Build a beautiful cookbook — an art-directed PDF and a validated, reflowable
EPUB — from a folder of markdown recipes.**

Recipes are plain markdown files with a little YAML front matter. `ladle` turns
the whole collection into a print-ready PDF (via WeasyPrint) and an
epubcheck-clean EPUB (via pandoc), driven by one `book.yaml` and a swappable
**theme** for the look. The design (fonts, palette, layout) is fully decoupled
from the content, so the same recipes can render under any theme, and any book
can bring its own.

> A full worked example — 11 recipes, stories, illustrations, the works — lives
> in [`examples/community-cookbook/`](examples/community-cookbook/). That is the
> book this tool grew out of; it now ships as the reference example.

## Install

```sh
pip install ladle
```

`ladle` is Python plus two small command-line tools (one runtime, no browser,
no Node):

| Tool | Version | Used for |
| --- | --- | --- |
| Python | 3.11+ | the tool itself |
| pandoc | 3.x | EPUB generation |
| poppler | any recent | `pdfinfo` + `pdftoppm` (PDF checks, EPUB cover) |
| Java | 17+ | optional — only to run `epubcheck` in `ladle validate` |

[WeasyPrint](https://weasyprint.org) (a dependency) needs the Pango/cairo system
libraries:

- **macOS:** `brew install pango poppler pandoc`
- **Debian/Ubuntu:** `sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 poppler-utils pandoc`

Run `ladle doctor` to check everything is present, with per-OS install hints.

## Quickstart

```sh
ladle new mybook                 # scaffold books/mybook/ (book.yaml + a draft recipe)
cd books/mybook
# …add your recipes under recipes/…
ladle build                      # -> build/cookbook.pdf and build/cookbook.epub
ladle validate                   # schema + PDF structure + epubcheck + contact sheet
open build/contact-sheet.png
```

Book-scoped commands take `--book PATH` (default: `$BOOK_CONFIG` or
`./book.yaml`), so you can keep several books side by side and build any of them.

## Commands

| Command | Does |
| --- | --- |
| `ladle new [--name X]` | scaffold a new book under `books/X/` |
| `ladle build` | build PDF + EPUB (`html` → `pdf` → `epub`) |
| `ladle html` / `pdf` / `epub` | run a single stage |
| `ladle validate` | recipe schema, PDF trim + page count, epubcheck, contact sheet |
| `ladle illustrations` | (re)generate the SVG placeholder art |
| `ladle assets [--theme DIR]` | re-bake a theme's raster brand assets (paper grain, patterns) |
| `ladle doctor` | check pandoc/poppler/WeasyPrint/Java are installed |

## A book

```text
mybook/
  book.yaml            # title, language, theme, palette/font overrides, section order
  recipes/*.md         # one recipe per file (front matter + body)
  content/introduction.md
  assets/illustrations/recipes/*   # generated per-recipe art (real art drops in as PNG)
```

`book.yaml` needs only a `title` to build — everything else (palette, fonts,
labels) falls back to the theme's defaults. Point `theme:` at a bundled theme by
name (`default`) or at your own theme directory.

### Recipe format

```markdown
---
title: Carrot Cake
category: Desserts            # Savory | Desserts | Beverages
servings: "6 people"          # optional — omit when the source gives no quantity
credits: "Marine Gora, Café Gramme, Paris"   # optional — omit when there's no named source
illustration: assets/illustrations/recipes/carrot-cake.svg
# optional: page, story, author:{name,org}, headshot, attribution, tags, license, draft
---

## INGREDIENTS

### Cake                      # optional group headings
- 2 large eggs
- 200g sugar

## DIRECTIONS

1. Pre-heat the oven to 180°C.
2. …

## NOTES                      # optional
- Keeps for several days.
```

A recipe with a non-empty `story:` gets a full story page (with optional
`headshot`); without one it gets a compact opener. Every recipe is validated
against [`src/ladle/schema/recipe.schema.json`](src/ladle/schema/recipe.schema.json).

Section headings (`## INGREDIENTS` etc.) and all UI chrome ("Yields",
"Contents", section names) are localizable per book via a `labels:` block in
`book.yaml` — see the example book for a template.

## Themes

The look is a **theme**: a self-contained bundle of `theme.yaml` (palette,
fonts, font files) plus `templates/`, `css/`, `fonts/`, and
`illustrations/patterns/`. The tool ships one theme, `default`. To restyle,
override tokens in `book.yaml`, or fork the theme and point `theme:` at it. See
[docs/THEMING.md](docs/THEMING.md).

## Illustrations

Each recipe ships with an on-brand **SVG placeholder** (`ladle illustrations`),
so builds are always green. To add real artwork, generate it in any image model
using the theme's locked style and save it as
`assets/illustrations/recipes/<slug>.png` (transparent PNG) next to the
placeholder — the build prefers the raster automatically, no front-matter change.

## Developing the tool (from a checkout)

```sh
git clone https://github.com/dimitri-kandassamy/ladle && cd ladle
pip install -e .                 # or: pip install -r requirements.txt
make all                         # builds the example book (examples/community-cookbook)
make validate
```

`make` drives the package straight from `src/` (no install needed):
`make all BOOK=path/to/book.yaml` builds any book. The `Makefile` targets mirror
the CLI commands. CI (`.github/workflows/build.yml`) builds + validates the
example book and a torture-test fixture on every push.

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

## Licensing

- **Code** (the tool, themes, CSS, templates): Apache-2.0 — see [`LICENSE-CODE`](LICENSE-CODE).
- **Content** (the example book's recipes, stories, illustrations): CC BY-SA 4.0
  — see [`LICENSE-CONTENT`](LICENSE-CONTENT), unless a recipe's `license:` says otherwise.
