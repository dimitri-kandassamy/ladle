# The Community Cookbook

A beautifully designed, community-sourced cookbook. Recipes are plain markdown
files; a Python build pipeline turns the whole collection into an art-directed
**PDF** and a reflowable, validated **EPUB**, published automatically on every
change.

Recipes, stories, and illustrations are all original, contributed by people who
love to cook.

## What's in the box

| Area | Where |
| --- | --- |
| Content | `recipes/*.md` (YAML front matter + body), `content/introduction.md`, `book.yaml` |
| Design | OFL fonts (Playfair Display + Bitter), CSS in `assets/css/`, Jinja templates in `templates/` |
| Art | original illustrations in `assets/illustrations/` (SVG placeholders ship; real art drops in as PNG) |
| Build | `tools/` (Python), orchestrated by the `Makefile` |
| CI | `.github/workflows/build.yml` — lint, validate, build, and release |

See [DESIGN.md](DESIGN.md) for the architecture and [CONTRIBUTING.md](CONTRIBUTING.md)
for the full contributor guide.

## Requirements

The build is Python plus two small command-line tools. One language runtime, no
browser, no Node.

| Tool | Version | Notes |
| --- | --- | --- |
| Python | 3.11+ | `pip install -r requirements.txt` |
| pandoc | 3.x (CI pins 3.10) | EPUB generation |
| poppler | any recent | `pdfinfo` + `pdftoppm` (PDF checks, cover) |
| Java | 17+ | optional, only to run `epubcheck` locally |

[WeasyPrint](https://weasyprint.org) (installed via `requirements.txt`) needs the
Pango/cairo system libraries:

- **macOS:** `brew install pango`
- **Debian/Ubuntu:** `sudo apt-get install libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 poppler-utils pandoc`

## Build it locally

```sh
pip install -r requirements.txt
make all          # -> build/cookbook.pdf and build/cookbook.epub
make validate     # schema + PDF structure + epubcheck + contact sheet
open build/contact-sheet.png
```

Individual targets: `make pdf`, `make epub`, `make illustrations`,
`make assets` (re-bake paper grain + patterns), `make clean`.

`epubcheck` runs in `make validate` when Java and the epubcheck jar are present;
otherwise it falls back to a structural EPUB check. CI always runs the full
validation.

## Add a recipe

1. Copy an existing file in `recipes/` to `recipes/<your-slug>.md`.
2. Fill in the front matter and the `## INGREDIENTS` / `## DIRECTIONS` body.
3. Run `make all && make validate`, eyeball `build/contact-sheet.png`, open a pull request.

CI validates every recipe against
[`schema/recipe.schema.json`](schema/recipe.schema.json) and rebuilds the book.

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
`headshot`); without one it gets a compact opener. Either way the look stays
consistent.

## Illustrations

Each recipe ships with an on-brand **SVG placeholder**
(`tools/gen_illustrations.py`), so builds are always green. To add real artwork,
generate it by hand in any image model using the locked watercolour-and-ink style
(documented in [DESIGN.md](DESIGN.md#illustrations)) and save it as
`assets/illustrations/recipes/<slug>.png` (transparent PNG). The build prefers
that raster over the placeholder automatically — no front-matter change.

## Releases

Git holds the meaningful history (the markdown source); the built PDF and EPUB are
reproducible and not versioned per build.

- Every push to `main` refreshes a single rolling `latest` release, at a stable
  URL: `…/releases/download/latest/cookbook.pdf` (and `.epub`).
- To cut a citeable edition, bump `volume` in `book.yaml` and push a tag:

  ```sh
  git tag v1.0 && git push origin v1.0
  ```

  CI publishes a versioned release for it (the newest tagged edition gets the
  _Latest_ badge). GitHub Pages deploy is opt-in via the `ENABLE_PAGES=true`
  repository variable.

## Licensing

- **Code** (tools, templates, CSS): Apache-2.0 — see [`LICENSE-CODE`](LICENSE-CODE).
- **Content** (recipes, stories, illustrations): CC BY-SA 4.0 — see
  [`LICENSE-CONTENT`](LICENSE-CONTENT), unless a recipe's `license:` says otherwise.
