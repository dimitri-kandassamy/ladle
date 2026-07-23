# Theming `ladle`

A **theme** is a self-contained design bundle. The tool ships one built-in
theme, `default` (the Community Cookbook art direction), and a book selects a
theme with one line in its `book.yaml`:

```yaml
theme: default            # a bundled theme, by name
# theme: themes/mine      # …or a path, resolved relative to this book.yaml
# theme: /abs/path/theme  # …or an absolute path
```

Design (the theme) and content (the book) are fully decoupled: the same recipes
render under any theme, and a theme carries its own fonts, so nothing about the
look is hardcoded in the tool.

## Anatomy of a theme

```text
mytheme/
  theme.yaml                     # manifest: tokens + font declarations
  templates/
    print.html.j2                # WeasyPrint (PDF) layout
    epub.html.j2                 # pandoc (EPUB) semantic HTML
  css/
    common.css  print.css  epub.css
  fonts/
    *.ttf                        # the fonts this theme embeds
  illustrations/
    patterns/                    # decorative art + baked paper textures
```

Two structural rules the build depends on:

1. **`css/` and `illustrations/patterns/` must stay siblings.** `print.css`
   references textures with `url(../illustrations/patterns/…)`, resolved
   relative to the CSS file. Keep the layout above and those links just work.
2. **Every font named in `theme.yaml`'s `font_faces` must exist in `fonts/`.**

## `theme.yaml`

The manifest is validated on load against `schema/theme.schema.json`
(`additionalProperties: false`), so a typo'd key or a malformed `font_faces`
entry fails with a clear error instead of being silently dropped. **`name` is
the only required field;** everything else is optional.

The metadata fields below (`version`, `ladle`, `author`, `license`, `tags`,
`preview`, `fonts_meta`) are validated for shape but **not yet consumed** — they
declare a theme's provenance for forthcoming tooling (a gallery, compatibility
checks, a linter). In particular `ladle:` does *not* yet gate on core version.

```yaml
name: mytheme                   # required — the theme's identifier
title: My Theme                 # optional — display name for listings
description: One-line description of the look.

# Optional metadata (portable, ownable bundle — used by tooling/galleries):
version: "1.0.0"                # theme version (semver), independent of ladle core
ladle: ">=0.2,<1.0"             # compatible ladle core version range
author: { name: "You", handle: "@you", url: "https://…" }
license: CC-BY-4.0              # license for the theme's design assets
tags: [warm, rustic, serif]     # mood/style tags for gallery filtering
preview: previews/cover.png     # generated preview image (path in this theme dir)

# Default design tokens. A book.yaml overrides any key, so these are the
# fallback a minimal book (just a title) renders with.
palette:
  navy: "#16203a"
  cream: "#faefdb"
  ink: "#3c3c3c"
  ink_deep: "#231f20"
  rule: "#c9bfa6"

fonts:
  display: "Playfair Display"   # headings
  body: "Bitter"                # body text

# Fonts embedded in the PDF (@font-face) and EPUB. family = CSS name,
# file = a file under this theme's fonts/, style = normal | italic.
font_faces:
  - { family: "Playfair Display", file: "PlayfairDisplay.ttf", style: normal }
  - { family: "Playfair Display", file: "PlayfairDisplay-Italic.ttf", style: italic }
  - { family: "Bitter", file: "Bitter.ttf", style: normal }
  - { family: "Bitter", file: "Bitter-Italic.ttf", style: italic }

# Optional license provenance per embedded font family.
fonts_meta:
  - { family: "Playfair Display", license: "OFL-1.1", source: "https://fonts.google.com/specimen/Playfair+Display" }
  - { family: "Bitter", license: "OFL-1.1", source: "https://fonts.google.com/specimen/Bitter" }
```

### Token precedence

`theme.yaml` tokens are **defaults**; a book's `book.yaml` overrides them per
key. So one theme can back many books that differ only in palette — e.g. a
book overriding `palette.navy` while keeping everything else.

The templates expose tokens as CSS variables (`--navy`, `--cream`, `--ink`,
`--ink-deep`, `--rule`, `--display`, `--body`), so most restyling is CSS + token
edits, no template surgery.

## What a template receives

Both templates get `book` (the merged `book.yaml`, with `book.labels` for every
printed string) and `recipes` — an ordered list of recipe objects:

| Key                                  | What it is                                        |
| ------------------------------------ | ------------------------------------------------- |
| `slug` `title` `category` `servings` | front matter, as written                          |
| `credits` `page` `credits_line`      | provenance; `credits_line` folds in `p. N`        |
| `author.name` `author.org`           | empty strings when there is no `author:`          |
| `has_story` `story_html`             | `story_html` is a list of paragraphs              |
| `headshot_url` `illustration_url`    | empty string when unset — **always guard**        |
| `ingredients_html` `directions_html` | **rendered HTML** for each section                |
| `notes_html`                         | **rendered HTML**; empty when there is no section |
| `extra_sections`                     | `[{title, html}]` for unknown headings            |
| `attribution` `draft`                | front matter                                      |

### Section bodies are rendered HTML

ladle splits a recipe body on its `##` headings and renders each section from
markdown, so a template inserts one value per section rather than looping:

```jinja
<div class="ing-body">{{ r.ingredients_html }}</div>
<div class="steps">{{ r.directions_html }}</div>
```

You get plain `<p>`, `<ul>`, `<ol>`, `<h3>` and inline `<a>/<strong>/<em>` — no
ladle-specific classes — so style them under a wrapper your template owns. Use
the child combinator where nesting matters:

```css
.steps > ol { counter-reset: step; list-style: none; }
.steps > ol > li::before { content: counter(step) "."; }
```

Always render `extra_sections`, or a book using a heading ladle doesn't know
will lose it:

```jinja
{% for s in r.extra_sections %}
  <h2 class="label">{{ s.title }}</h2>
  <div class="prose">{{ s.html }}</div>
{% endfor %}
```

> **Breaking change.** `r.ingredient_groups` and `r.directions` are gone,
> replaced by `r.ingredients_html` / `r.directions_html`, and `r.notes_html` is
> now one HTML value rather than a list of paragraphs. The names changed
> deliberately: a template still referencing the old ones fails loudly on an
> undefined variable instead of quietly iterating a string character by
> character. `r.story_html` is unchanged.

## Authoring workflow

The quickest start is to fork `default`:

```sh
# copy the built-in theme into your book and point book.yaml at it
cp -r "$(python3 -c 'import ladle,pathlib;print(pathlib.Path(ladle.__file__).parent/"themes/default")')" themes/mine
# edit themes/mine/theme.yaml (palette/fonts), css/, templates/ …
# in book.yaml:  theme: themes/mine
ladle build --book book.yaml && ladle validate --book book.yaml
```

### Linting a theme

You may build and use *any* theme at your own risk — themes install by path,
with no gate. A theme shown in the **community gallery**, though, must lint
clean:

```sh
ladle theme lint themes/mine   # or a bundled name: ladle theme lint default
```

`theme lint` runs three checks:

- **manifest** — `theme.yaml` exists and validates against the theme schema;
- **sandbox** — `print.html.j2`/`epub.html.j2` are present and load in the Jinja
  sandbox (theme templates are rendered as untrusted data, never code);
- **fonts** — every family in `font_faces` names a file that exists and has a
  documented, redistribution-friendly license in `fonts_meta` (OFL, Apache,
  UFL, MIT, …).

It exits non-zero if any check fails, so it drops straight into CI.

### Previewing a theme

To see what a theme actually looks like, render it against the bundled canonical
sample book — a tiny, asset-free book with one recipe per section, so the cover,
contents, a recipe opener, and a method page all appear:

```sh
ladle theme preview themes/mine   # or a bundled name: ladle theme preview default
```

It writes to `build/preview/<theme>/`:

- `cookbook.pdf` — the full render (the print art direction, ladle's differentiator);
- `cover.png` and `contact-sheet.png` — quick images for eyeballing or a gallery
  card (produced when poppler's `pdftoppm` is available; skipped otherwise, PDF
  still written).

Pass `--book PATH` to preview a theme against your own book instead of the sample.

### Paper textures

The cream/navy paper grain and the cover/endpaper line-art are pre-baked raster
files (`paper-cream.jpg`, `paper-navy.png`, `cover.png`, `endpaper.png`) committed
under the theme's `illustrations/patterns/`, alongside the source SVGs they were
rasterised from. The PDF build consumes the rasters directly.

If you change a theme's `palette.cream` or `palette.navy`, regenerate these files
so the textures match and commit the results with your theme. The tool no longer
ships a baking command — edit the source SVGs and rasterise them with your own
tooling (the reference implementation lives in the project's git history at
`src/ladle/bake_assets.py`).

## Checklist for a new theme

- [ ] `theme.yaml` with a `name`, `palette`, `fonts`, and a `font_faces` entry per file
- [ ] `fonts/` contains every file referenced in `font_faces` (+ their licenses)
- [ ] `templates/print.html.j2` and `templates/epub.html.j2`
- [ ] `css/common.css`, `css/print.css`, `css/epub.css`
- [ ] `illustrations/patterns/` with `cover.svg`/`endpaper.svg` and baked rasters
- [ ] `fonts_meta` documents each family's license (required by `ladle theme lint`)
- [ ] `ladle theme lint` passes (schema + sandbox + fonts)
- [ ] `ladle build` + `ladle validate` pass against a test book
