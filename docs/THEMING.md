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
    patterns/                    # baked paper textures (and any art you add)
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

Two rules make that override actually take effect, and a theme has to honour
both — they are the whole cascade contract:

1. **The token `<style>` block is emitted last in the `<head>`**, after every
   `<link>`. `print.html.j2` interpolates `{{ book.palette.* }}` /
   `{{ book.fonts.* }}` into a `:root` block; put it above the links and any
   stylesheet declaring `:root` outranks it, because equal specificity means the
   later rule wins.
2. **No stylesheet declares `:root`.** Defaults belong in `theme.yaml`, which is
   the only place the merge reads them from. Declaring them in CSS as well is
   what silently discarded every book override before ladle 0.3.

If you fork the bundled theme, keep the `<link>`-then-`<style>` order in
`print.html.j2`. A quick check on any book that sets a `palette:` override: the
value you asked for should appear in `build/cookbook.html`'s **last** `:root`
block, with nothing after it that redeclares the same variable.

One caveat specific to the bundled theme: `palette.navy` and `palette.cream` are
the page grounds, and `.page.navy`/`.page.cream` tile an **opaque** paper texture
over the colour. Overriding either reaches the cascade but is hidden behind that
raster, so it also needs the textures regenerated (see
[Paper textures](#paper-textures) below). The type tokens — `ink`, `ink_deep`,
`rule`, `display`, `body` — take effect on their own.

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

### `toc` — the sections, already grouped

Both templates also get `toc`: the same recipes grouped into ordered sections,
ready to iterate.

| Key       | What it is                                          |
| --------- | --------------------------------------------------- |
| `name`    | the category as recipes write it — the matching key |
| `title`   | the displayed name, via `book.labels.section_names` |
| `recipes` | that section's recipes, in book order               |

```jinja
{% for section in toc %}
  <h2>{{ section.title }}</h2>
  <ul>{% for r in section.recipes %}<li><a href="#{{ r.slug }}">{{ r.title }}</a></li>{% endfor %}</ul>
{% endfor %}
```

Iterate `toc`, never `book.sections`. That key is optional — most books never set
it, and a template that read it printed an empty contents page for all of them.
`toc` is derived instead: a book that declares `sections:` gets them in that
order, a book that declares none gets one section per category its recipes use,
and either way every recipe in the book has an entry. It is empty only when the
book has no recipes.

This is the general rule: **a template receives derived structures, never raw
configuration.** If you find yourself reading a `book.yaml` key the core doesn't
pre-compute, that is a gap in the context worth filing rather than reading around.

### Deciding how many pages a recipe gets

`directions_html` and `illustration_url` are empty strings, not missing keys, so
a template can branch on what a recipe actually carries. The bundled theme uses
exactly two such branches, and a theme with a fixed-height sheet wants both:

- **`has_story` or `illustration_url`** → an opener page (story or hero) plus a
  method page. With neither, an opener would be a title alone on blank paper, so
  the bundled theme sets those recipes on a single sheet instead.
- **`directions_html` empty** → the author recorded only the ingredients. Print
  `book.labels.no_method` where the steps would start and drop the column
  divider; a labelled empty column beside a hairline reads as an unfinished page.

Both are content-keyed on purpose. Nothing in `book.yaml` selects a layout, so a
book gains or loses the spread by gaining or losing art.

### Section bodies are rendered HTML

ladle splits a recipe body on its `##` headings and renders each section from
markdown, so a template inserts one value per section rather than looping:

```jinja
<div class="ing-body">{{ r.ingredients_html }}</div>
<div class="steps">{{ r.directions_html }}</div>
```

You get plain `<p>`, `<ul>`, `<ol>`, `<h3>` and inline `<a>/<strong>/<em>`, with
one exception noted below — so style them under a wrapper your template owns.
Use the child combinator where nesting matters:

```css
.steps > ol { counter-reset: step; list-style: none; }
.steps > ol > li::before { content: counter(step) "."; }
```

### `a.xref` — the one class ladle emits

A `[Label](#slug)` in a recipe body is an in-book cross-reference to the recipe
with that slug, and renders as `<a class="xref" href="#slug">`. It is the only
ladle-specific class in a rendered body, and it exists because print needs
something the markup can't say on its own: a hyperlink is useless on paper
without a page number.

Give it one, the same way the bundled theme's table of contents does — the
number resolves at render time against the target's `id`, so it stays right
however the book repaginates:

```css
.xref::after { content: " (p. " target-counter(attr(href url), page) ")"; }
```

Scope that to your print stylesheet. In the EPUB the anchor is a working
hyperlink already, and pandoc rewrites it across the chapter split for you.
Themes are free to ignore the class entirely — the reference then reads as plain
text, still linked.

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
contents, and a recipe page all appear (the sample ships no art, so its recipes
render on single sheets):

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

The cream and navy paper grain are pre-baked raster files (`paper-cream.jpg`,
`paper-navy.png`) committed under the theme's `illustrations/patterns/`. The PDF
build consumes them directly.

Grain is the only decoration the bundled theme ships. It used to lay a scattered
line-art motif over the navy pages as well; that was dropped, because type set
over it — a cover title, a section name — always had to fight it for legibility.
Your own theme is free to add art back, but put it where nothing has to be read
on top of it.

If you change a theme's `palette.cream` or `palette.navy`, regenerate these files
so the textures match and commit the results with your theme. The tool no longer
ships a baking command — edit the source SVGs and rasterise them with your own
tooling (the reference implementation lives in the project's git history at
`src/ladle/bake_assets.py`).

## Checklist for a new theme

- [ ] `theme.yaml` with a `name`, `palette`, `fonts`, and a `font_faces` entry per file
- [ ] `fonts/` contains every file referenced in `font_faces` (+ their licenses)
- [ ] `templates/print.html.j2` and `templates/epub.html.j2`
- [ ] `css/common.css`, `css/print.css`, `css/epub.css` — none of them declaring `:root`
- [ ] `print.html.j2` emits its `<link>` tags before the token `<style>` block
- [ ] `illustrations/patterns/` with any baked rasters `print.css` references
- [ ] `fonts_meta` documents each family's license (required by `ladle theme lint`)
- [ ] `ladle theme lint` passes (schema + sandbox + fonts)
- [ ] `ladle build` + `ladle validate` pass against a test book
