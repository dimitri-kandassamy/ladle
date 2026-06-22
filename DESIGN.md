# Plan: Community Cookbook — beautifully-designed PDF + EPUB generator

> **Status:** historical design rationale. This is the original approved plan; some details
> have since evolved — illustrations are now hand-generated from prompts in `ILLUSTRATIONS.md`
> (no in-repo AI API), every recipe uses the two-page opener + method layout, and the cream
> paper grain is baked from an SVG filter. See `README.md` for the current workflow.

## Context

The user supplied *The Cloud Native Community Cookbook* (Equinix, InDesign) as a **design
reference**. Its recipes, stories, photos, illustrations and commercial fonts (FreightBigPro,
Sentinel) are copyrighted and will **not** be reproduced. The goal is a **new open-source
generator** that *evokes that art direction* with only free/original assets, driven by
community-contributed recipe markdown, and **auto-published as a beautiful PDF and a reflowable
EPUB**.

The user already has **11 recipes** in an existing repo
(`/Users/aznaar/Code/dimitri-kandassamy/cookbook`, Apache-2.0) in a **heading-based** format
(no YAML frontmatter) plus a draft `SPEC.md` (a Hugo-style EPUB CLI, not yet implemented). Those
recipes will be **migrated** into this new project's frontmatter schema.

### User decisions (locked)
- **New project**, fresh git repo, to be published under the **`dimitri-kandassamy` GitHub org**
  (working name `community-cookbook`; local path `/Users/aznaar/Code/dimitri-kandassamy/community-cookbook`).
- **Outputs:** art-directed **PDF** *and* reflowable **EPUB**.
- **Illustrations:** **AI-generated, one locked style** (own content).
- **PDF engine:** **Chromium + Paged.js** (max print-CSS fidelity).
- **EPUB engine:** **pandoc** (reflowable, validated with epubcheck).
- **Publish:** **GitHub Actions → Releases + GitHub Pages**.
- **Story page:** **optional with graceful fallback** — recipes with a `story` get the full
  Cloud-Native-style story page (+ optional headshot); recipes without get a compact opener
  (title + credit + hero illustration). All 11 current recipes start without stories.
- **Fonts:** free OFL substitutes (commercial originals can't ship).

### Reverse-engineered design facts (from the reference PDF)
- Trim **486×684 pt = 6.75″×9.5″** portrait. Palette: navy `#16203a`, cream `#faefdb`, dark ink.
- Page archetypes: **cover** (navy + white line-art food pattern + title block) · **endpaper**
  (full-bleed navy line-art) · **introduction** (cream, story) · **recipe story page** (display
  title, "RECIPE BY" byline, circular headshot, story, hero illustration, running footer) ·
  **recipe method page** (two columns Directions/Ingredients + a *vertical rotated sidebar* with
  recipe name + author up the outer edge, spot illustrations, footer) · **colophon / back cover**.
- Type: high-contrast Didone display + Clarendon slab body + letter-spaced small-caps labels.
- Ingredients are **grouped** (e.g. DOUGH / FILLING / DRESSING); directions are numbered.

### Environment confirmed
python3 3.11 (Jinja2, PyYAML, Pillow, PyMuPDF), node v26 + npm/npx, pandoc 3.10, Google Chrome
installed, poppler + ghostscript, network up. To add: npm `pagedjs-cli`, `epubcheck`; python
`markdown`; OFL font files.

### Honest constraint
No image-generation tool/API key in this environment, so AI art can't be *run* here. The full
pipeline (locked-style prompt templates + a generator that calls an image model when an API key is
set) will be built, and **deterministic on-brand SVG placeholders** ship so every build is green
now. Swapping in real AI art is a drop-in, no layout change.

---

## Architecture: one semantic source → two renderers

```
recipes/*.md (frontmatter + body) + content/*.md + book.yaml   ← single source of truth
                 │ validate against schema/recipe.schema.json
        ┌────────┴───────────────────────────────┐
        ▼ tools/build_html.py (Jinja2)            ▼ tools/build_html.py --epub
   art-directed HTML + print.css             semantic HTML + epub.css
        ▼ tools/make_pdf.mjs                       ▼ tools/make_epub.sh
   pagedjs-cli → Chromium → cookbook.pdf      pandoc → cookbook.epub (+ epubcheck)
```

This is also where the existing `SPEC.md` vision converges: this project realizes its
**build/theme/publish** layer for PDF+EPUB; the `ingest`/Ollama CLI remains future work that can
feed the same `recipes/*.md`.

## Recipe frontmatter schema (reconciles SPEC §8 + the art direction)

```yaml
---
title: Carrot Cake
slug: carrot-cake                 # derived from filename if omitted
category: Desserts                # Desserts | Savory | Beverages (migrated from README)
tags: [cake]
servings: "6 people"              # migrated from "### YIELDS"
credits: "Marine Gora, Café Gramme, Paris"   # migrated from "## CREDITS"
attribution: ""                   # optional "Based on a recipe by …" footer line
story: ""                         # OPTIONAL narrative → triggers full story page
author: { name: "", org: "" }     # OPTIONAL story byline (RECIPE BY …)
headshot: ""                      # OPTIONAL path; circular crop on story page
illustration: assets/illustrations/recipes/carrot-cake.svg   # hero food art (placeholder ok)
license: CC-BY-SA-4.0             # per-recipe content license (default inherits book.yaml)
draft: false
---

## INGREDIENTS
### Cake
- 2 large eggs
- …
### Frosting
- …

## DIRECTIONS
1. …

## NOTES        (optional)
- …
```

Metadata lives in frontmatter; body holds only INGREDIENTS (with optional `###` groups),
DIRECTIONS, optional NOTES. `build_html.py` parses the body into structured ingredient
groups/steps for the PDF; pandoc renders the same markdown semantically for EPUB.

## Migration of the 11 existing recipes (`tools/migrate.py`, one-off)
Reads each `../cookbook/Recipes/*.md` and writes the new frontmatter form:
- Title from `# …`; split trailing "by <Name>" (e.g. *Chocolate Fondant by Celine Pham*) into
  `credits` when no CREDITS section.
- `### YIELDS` → `servings`; `## CREDITS` → `credits`; category from the README mapping
  (Desserts / Savory / Beverages); keep INGREDIENTS (groups preserved), DIRECTIONS, NOTES in body.
- `story`/`author`/`headshot` left empty (graceful fallback opener).
- Assign a placeholder `illustration` per slug. Output reviewed by `validate.py`.

## Repository layout (`community-cookbook/`)
```
community-cookbook/
├── DESIGN.md (this plan)  README.md  CONTRIBUTING.md  CODE_OF_CONDUCT.md
├── LICENSE-CODE (Apache-2.0, matching the user's ecosystem)  LICENSE-CONTENT (CC BY-SA 4.0)
├── book.yaml                      # title, volume, palette, fonts, recipe order, colophon
├── content/introduction.md
├── recipes/                       # 11 migrated recipes (frontmatter + body)
├── schema/recipe.schema.json
├── assets/
│   ├── fonts/                     # Playfair Display + Bitter (OFL .ttf + licenses)
│   ├── css/  common.css print.css epub.css
│   └── illustrations/
│       ├── patterns/ cover.svg endpaper.svg back.svg   (navy line-art placeholders)
│       └── recipes/  <slug>.svg + headshots/           (placeholders)
├── templates/ base.html cover.html endpaper.html intro.html
│              recipe-story.html recipe-method.html colophon.html
├── tools/ build_html.py  make_pdf.mjs  make_epub.sh  gen_illustrations.py
│          migrate.py  validate.py
├── build/                         # outputs (gitignored)
├── package.json  Makefile  .gitignore  .markdownlint.json
└── .github/workflows/build.yml    # PR: validate+build; main: build→release→pages
```

## Design system (free)
- Display ← FreightBigPro Black → **Playfair Display** 900 + Black Italic.
- Body ← Sentinel slab → **Bitter** (regular/italic/bold).
- Labels/footer: Bitter uppercase + letter-spacing for the small-caps look.
- `--navy:#16203a; --cream:#faefdb; --ink:#23252b; --rule:#c9bfa6`.
- `print.css`: `@page{size:6.75in 9.5in;margin:0}` full-bleed backgrounds; `writing-mode:vertical-rl`
  sidebar; flexbox two-column method; named pages + per-recipe page breaks; running footer.
- `epub.css`: reflowable — same palette/fonts; hero illustration scales; sidebar demoted to a
  heading; ingredients/directions stack on narrow screens.

## Build pipeline
1. `build_html.py` — load `book.yaml`, glob `recipes/`, validate against schema (fail on error),
   parse body → structured recipe, render Jinja in book order → `build/cookbook.html` (print) and
   `build/epub.html` (semantic). Chooses story-page vs compact-opener per `story` presence.
2. `make_pdf.mjs` — `pagedjs-cli build/cookbook.html -o build/cookbook.pdf` via installed Chrome
   (`PUPPETEER_EXECUTABLE_PATH`), embedding fonts.
3. `make_epub.sh` — `pandoc build/epub.html -o build/cookbook.epub` with metadata, cover, epub.css,
   embedded fonts; then `epubcheck`.
4. `gen_illustrations.py` — idempotent; locked style = constant prompt prefix + per-recipe subject
   from frontmatter; writes missing art only; placeholder fallback when no API key.

## Validation (the "compare to reference", reframed)
Content/art intentionally diverge, so validation is **structural + art-direction**, not pixel:
- JSON-schema validation of every recipe (CI gate); markdownlint retained.
- `validate.py` asserts page archetypes exist + invariants (cover first, endpapers present, each
  recipe = opener[/story] + method page(s), footer present, PDF trim = 6.75×9.5).
- Render our PDF → PNG (pdftoppm) → `build/contact-sheet.png` next to the reference for eyeballing.
- `epubcheck` must pass.

## CI (`.github/workflows/build.yml`)
- **PR:** setup python+node+pandoc → install deps → `make validate` → `make all` (artifacts only).
- **push main:** `make all` → create/update GitHub **Release** with `cookbook.pdf`+`cookbook.epub`
  → build landing page → deploy to **GitHub Pages**. Pinned tool versions for reproducibility.

## Implementation order
0. Scaffold repo; copy this plan to `DESIGN.md`; `git init`; add LICENSE/README/CONTRIBUTING,
   `.gitignore`, `book.yaml`, `schema/recipe.schema.json`.
1. `migrate.py` → convert the 11 recipes; eyeball-review output.
2. Fonts (OFL) + `assets/css/*` + `templates/*`; `build_html.py` print path.
3. `make_pdf.mjs` → first real `cookbook.pdf` (the spine). Iterate on fidelity vs reference.
4. `gen_illustrations.py` placeholders (patterns + per-recipe spots) so pages aren't empty.
5. EPUB path: `build_html.py --epub` + `make_epub.sh` + `epub.css` → valid `cookbook.epub`.
6. `validate.py` + contact sheet; `Makefile` targets `pdf|epub|all|validate|clean`.
7. `.github/workflows/build.yml` (validate → build → release → pages).
8. README/CONTRIBUTING: how to add a recipe, the frontmatter schema, enabling AI art.

## Verification (prove it before handing back)
- `make all` → `build/cookbook.pdf` (6.75×9.5 trim, navy cover, cream recipe pages, two-column
  method + vertical sidebar, story pages where present) and validated `build/cookbook.epub`.
- `make validate`: schema + structural asserts + `epubcheck` pass; contact sheet generated.
- Open contact sheet to confirm the look matches the reference's art direction.
- Lint the workflow YAML; dry-run build steps locally.

## Risks / calls
- **Font feel:** Playfair+Bitter ≈ but ≠ the originals; swappable in `book.yaml`.
- **Paged.js + Chrome in CI:** uses GitHub-hosted browser; versions pinned.
- **AI art not runnable here:** placeholders now; real generation is a documented drop-in.
- **Two licenses:** Apache-2.0 (code, matching the user's repos) + CC BY-SA 4.0 (content);
  confirm content license preference at implementation.
```
