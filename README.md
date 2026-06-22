# The Community Cookbook

A beautifully designed, **community-sourced** cookbook. Recipes are plain markdown
files; a build pipeline turns the whole collection into an art-directed **PDF** and a
reflowable, validated **EPUB**, published automatically on every change.

> Inspired by the art direction of *The Cloud Native Community Cookbook* (© Equinix, Inc.),
> but built entirely from **original/free content**: our own recipes, OFL fonts, and our
> own illustrations. None of the reference's text, photos, illustrations, or fonts are used.

## What's in the box

| | |
|---|---|
| **Content** | `recipes/*.md` (YAML front matter + body), `content/introduction.md`, `book.yaml` |
| **Design** | OFL fonts (Playfair Display + Bitter), CSS in `assets/css/`, Jinja templates in `templates/` |
| **Art** | original illustrations in `assets/illustrations/` (SVG placeholders ship; real art is hand-generated from the prompts in [`ILLUSTRATIONS.md`](ILLUSTRATIONS.md)) |
| **Build** | `tools/` (Python + Node), orchestrated by the `Makefile` |
| **CI** | `.github/workflows/build.yml` → validate + build; pushes to `main` refresh a rolling `latest` release; `v*` tags cut versioned editions; Pages deploy is opt-in (`ENABLE_PAGES=true`) |

## Build it locally

Requirements: Python 3.11+, Node 18+, [pandoc](https://pandoc.org), Google Chrome,
poppler (`pdftoppm`/`pdfinfo`), and Java (for epubcheck — optional locally).

```sh
pip install -r requirements.txt
npm install                 # pagedjs-cli
make all                    # -> build/cookbook.pdf and build/cookbook.epub
make validate               # schema + PDF structure + epubcheck + contact sheet
open build/contact-sheet.png
```

Individual targets: `make pdf`, `make epub`, `make illustrations`, `make prompts`
(regenerate `ILLUSTRATIONS.md`), `make paper` (re-bake the cream texture), `make clean`.

## Add a recipe

1. Copy an existing file in `recipes/` (or follow the schema below) to
   `recipes/<your-slug>.md`.
2. Fill in the front matter and the `## INGREDIENTS` / `## DIRECTIONS` body.
3. `make all && make validate`, eyeball `build/contact-sheet.png`, open a pull request.

CI validates every recipe against [`schema/recipe.schema.json`](schema/recipe.schema.json)
and rebuilds the book. See [CONTRIBUTING.md](CONTRIBUTING.md) for the full guide.

### Recipe format

```markdown
---
title: Carrot Cake
category: Desserts            # Savory | Desserts | Beverages
servings: "6 people"
credits: "Marine Gora, Café Gramme, Paris"
illustration: assets/illustrations/recipes/carrot-cake.svg
# optional: story, author:{name,org}, headshot, attribution, tags, license, draft
---

## INGREDIENTS
### Cake                     # optional group headings
- 2 large eggs
- 200g sugar

## DIRECTIONS
1. Pre-heat the oven to 180°C.
2. …

## NOTES                     # optional
- Keeps for several days.
```

A recipe with a non-empty `story:` gets a full story page (with optional `headshot`);
without one it gets a compact opener. Either way the look stays consistent.

## Illustrations

Each recipe ships with an on-brand **SVG placeholder** (`tools/gen_illustrations.py`), so
builds are always green. Real artwork is generated **by hand in any image model** — there's
no API wiring in the repo. The workflow:

```sh
python3 tools/illustration_prompts.py     # writes ILLUSTRATIONS.md
```

[`ILLUSTRATIONS.md`](ILLUSTRATIONS.md) lists, for every recipe, a ready-to-paste **prompt**
and the recommended **size**, all in one locked watercolour-and-ink style so the set stays
coherent (tuned for Google's *nano banana* / Gemini 2.5 Flash Image, but model-agnostic).
For each recipe:

1. Paste the prompt into the image tool; generate at the recommended size (3:2 landscape)
   on a **transparent background** so the page's cream paper shows through.
2. Save the result as `assets/illustrations/recipes/<slug>.png` (transparent **PNG** or WebP —
   not JPEG, which can't hold transparency).
3. `make all` — the build automatically prefers that raster over the SVG placeholder, with
   **no front-matter edits**.

Re-run `tools/illustration_prompts.py` whenever you add recipes. The decorative navy
line-art pages stay procedural; `ILLUSTRATIONS.md` includes an optional prompt for those too.

## How it fits together

```
recipes/*.md + book.yaml ──► tools/build_html.py ──► build/cookbook.html ──► Paged.js+Chrome ──► PDF
                                       └──────────► build/epub.html   ──► pandoc ─────────────► EPUB
```

## Releases

This is a living book, so git holds the meaningful history (the markdown source); the
built PDF/EPUB are reproducible and aren't versioned per build. Instead:

- Every push to `main` refreshes a single **rolling `latest`** release — the always-current
  edition, at a stable URL: `…/releases/download/latest/cookbook.pdf` (and `.epub`).
- To cut a **citeable edition**, bump `volume` in `book.yaml` and push a tag:
  ```sh
  git tag v1.0 && git push origin v1.0
  ```
  CI publishes a versioned release for it (the newest tagged edition gets the *Latest* badge).

## Licensing

- **Code** (tools, templates, CSS): Apache-2.0 — see [`LICENSE-CODE`](LICENSE-CODE).
- **Content** (recipes, stories, illustrations): CC BY-SA 4.0 — see
  [`LICENSE-CONTENT`](LICENSE-CONTENT), unless a recipe's `license:` says otherwise.

See [`DESIGN.md`](DESIGN.md) for the full design + build rationale.
