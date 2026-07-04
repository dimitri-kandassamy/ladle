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

```yaml
name: mytheme
description: One-line description of the look.

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
```

### Token precedence

`theme.yaml` tokens are **defaults**; a book's `book.yaml` overrides them per
key. So one theme can back many books that differ only in palette — e.g. a
book overriding `palette.navy` while keeping everything else.

The templates expose tokens as CSS variables (`--navy`, `--cream`, `--ink`,
`--ink-deep`, `--rule`, `--display`, `--body`), so most restyling is CSS + token
edits, no template surgery.

## Authoring workflow

The quickest start is to fork `default`:

```sh
# copy the built-in theme into your book and point book.yaml at it
cp -r "$(python3 -c 'import ladle,pathlib;print(pathlib.Path(ladle.__file__).parent/"themes/default")')" themes/mine
# edit themes/mine/theme.yaml (palette/fonts), css/, templates/ …
# in book.yaml:  theme: themes/mine
ladle build --book book.yaml && ladle validate --book book.yaml
```

### Paper textures

The cream/navy paper grain and the cover/endpaper line-art are pre-baked raster
files under `illustrations/patterns/`. If you change a theme's `palette.cream`
or `palette.navy`, re-bake them so the textures match:

```sh
ladle assets --theme themes/mine
```

`ladle assets` reads the theme's `theme.yaml` palette, regenerates
`paper-cream.jpg` / `paper-navy.png`, and rasterizes `cover.svg` / `endpaper.svg`
to PNG. Commit the results with your theme.

## Checklist for a new theme

- [ ] `theme.yaml` with `palette`, `fonts`, and a `font_faces` entry per file
- [ ] `fonts/` contains every file referenced in `font_faces` (+ their licenses)
- [ ] `templates/print.html.j2` and `templates/epub.html.j2`
- [ ] `css/common.css`, `css/print.css`, `css/epub.css`
- [ ] `illustrations/patterns/` with `cover.svg`/`endpaper.svg` and baked rasters
- [ ] `ladle build` + `ladle validate` pass against a test book
