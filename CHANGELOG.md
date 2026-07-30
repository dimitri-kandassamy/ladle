# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking

- **A recipe without a story or an illustration now renders on one page.** The
  bundled theme's opener page exists to carry hero art; with no art and no story
  it was a title alone on an otherwise blank sheet — one per recipe, threaded
  through the whole book. Such a recipe is now set on a single sheet, its title
  block above its own columns. A recipe with a story or an illustration keeps its
  opener and method page exactly as before, so an illustrated book is unchanged
  (the example book's output is identical, still 16 pages); an art-free book gets
  dramatically shorter — a 75-recipe test book went 159 → 84 pages.

  The rule is keyed off the recipe's own content, not a book setting, so nothing
  needs configuring either way. `validate`'s page-count check knows the rule.

- **Theme templates receive rendered HTML for recipe section bodies.**
  `r.ingredient_groups` and `r.directions` are replaced by `r.ingredients_html`
  and `r.directions_html`, and `r.notes_html` is now a single HTML value instead
  of a list of paragraphs. New: `r.extra_sections` (`[{title, html}]`), which a
  template must render or a book using an unrecognised heading loses it.
  `r.story_html` is unchanged.

  The keys were renamed rather than reused on purpose: a template still
  iterating the old names now raises on an undefined variable instead of
  silently walking a string one character at a time. Section bodies emit plain
  `<p>`/`<ul>`/`<ol>`/`<h3>` with no ladle-specific classes, so themes style
  them under their own wrapper — see `docs/THEMING.md`, which now documents the
  full template context. Only the bundled theme is affected; the rendered output
  of the example book is byte-identical.

### Added

- **An interior title page.** The bundled theme went cover → endpaper → contents;
  it now sets the title quietly on paper first, as a printed book does. Front
  matter, so it carries no folio. One page longer.
- **`section_openers: true`** (`book.yaml`, default off) prints a full-page
  divider before each section — the section name between two rules on the navy
  ground — and nests each recipe under its section in the PDF outline. Off by
  default because a divider earns its sheet in a long book and crowds a short
  one: the bundled sample would spend three of them on three recipes.
- **Printed folios.** Every footer-bearing page (recipes and the introduction)
  now prints its page number above the running mark. The contents page has always
  resolved entries with `target-counter`, so until now it cited page numbers that
  no printed page carried — the numbers pointed nowhere on paper. Both read the
  same `counter(page)`, so a folio and its index entry cannot drift.
- **A recipe with no method reads as intentional.** When a recipe has ingredients
  but no `## DIRECTIONS` — ordinary in a hand-written archive — the theme prints
  `labels.no_method` where the steps would start and drops the column divider,
  instead of leaving a labelled empty column beside a hairline running into blank
  paper. New `labels:` key, overridable per book like the rest of the chrome.
- **Recipe cross-references.** `[Label](#slug)` in a recipe body links to another
  recipe by slug, emitted as `<a class="xref" href="#slug">`. A print theme can
  append the target's resolved page number (`target-counter`) so the reference
  never goes stale as the book repaginates; the EPUB keeps it a plain hyperlink.
  `build` warns per dead reference — `recipe.md:33: cross-reference to #x
  resolves to nothing` — because the alternative was an epubcheck failure
  (RSC-012) at `validate` time naming a generated chapter file and column.
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

- **The bundled theme drops its line art.** The navy pages — cover, endpapers,
  colophon — carried a scattered motif of jars and bowls behind their type. It
  competed with every line set over it (the cover title needed a panel to stay
  legible, and a section name over it was unreadable), and it pinned the theme to
  one decorative idea. The navy ground is now colour and paper grain alone, with
  the typography carrying those pages. This removes five raster and SVG assets,
  roughly halving the theme's asset weight; the cream paper grain is untouched.
- Theme templates now render in a `jinja2.sandbox.SandboxedEnvironment`, so an
  untrusted community theme is treated as data, never code; a template that trips
  the sandbox surfaces as a friendly error naming the file.
- **Recipe section bodies are now rendered as markdown.** ladle splits a body on
  its `##` headings and renders each section, instead of matching it against a
  line grammar that kept only `- item` / `### group` under `## INGREDIENTS` and
  numbered `1.` steps under `## DIRECTIONS`. Everything the old parsers dropped
  in silence now appears: a step wrapped onto a second line (which used to
  truncate mid-sentence while still reading as a complete one), a numbered
  ingredient list, an unbulleted ingredient, a prose lead-in, a `###` inside
  `## DIRECTIONS`. The supported markdown is documented in the README and
  covered by tests; anything outside it still renders, just unstyled.
- A `## HEADING` ladle does not know now renders as a generic titled block and
  warns, rather than vanishing — so a book written to another project's
  conventions builds on the first try and tells you what to rename. `build` and
  `validate` report it as `file:line: message`, capped in `build`;
  `validate --strict` still turns it into a failure.
- A missing `## INGREDIENTS`/`## DIRECTIONS`/`## NOTES` no longer implies a
  broken recipe: a drink or a cheese board legitimately has no method.
- A recipe whose front matter opens with `---` but never closes it now fails
  with a message naming the file, instead of a raw `ValueError` traceback.
- A `##` heading repeated within one recipe now accumulates its blocks; the
  earlier block used to be discarded.
- `validate`'s contact sheet is ~16x faster (a 224-page book went 147s -> ~9s in
  measurement): it rasterizes small glancing-resolution thumbnails instead of
  reading-resolution pages, across concurrent page-range workers.

### Fixed

- **Every scaffolded book printed an empty table of contents.** `ladle new`
  writes a `book.yaml` with `sections:` commented out, because it is optional.
  The contents page looped over `book.sections` directly, and Jinja iterates an
  undefined value as nothing — so the book built, exited 0, and printed a
  Contents page with a heading, a rule and no entries. Every first run produced
  it, and the EPUB disagreed silently, since pandoc builds its own navigation
  from the headings.

  Templates now receive `toc`, a grouping the core derives: declared sections in
  their declared order, then any category no section declares, each with its
  recipes. A book that sets `sections:` is unaffected; a book that sets none now
  gets one section per category its recipes use, and either way every recipe in
  the book has a contents entry — previously a recipe whose category was not
  declared printed but appeared nowhere in the front matter. Themes should
  iterate `toc` rather than `book.sections`; see `docs/THEMING.md`.

  A recipe with no usable `category:` is filed under a new `Uncategorized`
  bucket, which sorts last and prints as "Other Recipes" — a label a book
  overrides like any other. Such a book was always schema-invalid (`build` warns
  per file, `validate` fails it), but it still renders, and the old fallback
  filed those recipes under `Savory` — a claim the book had no basis for, which
  put cakes in with the stews. A `category:` written blank or with no value
  reached the contents page as an empty heading, or one reading "None"; both are
  now treated as absent. The bucket is assigned, never authored: it is not in the
  schema's enum, so no recipe can claim it directly.

  Templates in the themes ladle ships now also render with Jinja's
  `StrictUndefined`, so reading something the build does not pass is a named
  error instead of a blank region on the page. Your own themes are unaffected —
  that strictness waits for the theme API version field, since it would fail
  themes written against today's looser contract.

- **A book's `palette:` and `fonts:` overrides did nothing in the PDF.** The
  documented model is that `theme.yaml` tokens are defaults a `book.yaml`
  overrides per key. The merge was correct and the override was written into the
  page — but into a `<style>` block emitted *above* the `<link>` tags, while
  `common.css` declared the same `:root` variables again. Equal specificity, so
  the later rule won and the theme's own default overwrote the book's value every
  time. A book that set `palette.navy: "#ff0000"` still printed the theme's navy,
  which meant no book could restyle a theme without forking it. The EPUB was
  never affected: `epub.css` sets its type and colour directly rather than
  through the tokens — so it also does not yet honour the overrides, which is a
  separate gap.

  Fixed on both sides so the rule is explicit rather than incidental: the token
  block is now always **last** in the head, and `common.css` no longer declares
  `:root` at all. Defaults live in `theme.yaml`, which is the only place the merge
  reads them from — having them in two places is what made the bug possible.
  `docs/THEMING.md` documents both as a contract a forked theme has to keep.

  The bundled theme's own output is unchanged apart from one fallback: the
  effective `--body` stack loses `"Iowan Old Style"`, a macOS system font that
  only ever applied when the embedded `Bitter` failed to load. The example book's
  PDF extracts identical text and embeds the identical font set.

  One limit worth knowing before you reach for it: in the bundled theme,
  `palette.navy` and `palette.cream` are the *page grounds*, and those pages are
  painted with opaque baked paper textures (`illustrations/patterns/`) tiled over
  the colour. Overriding either now reaches the cascade but stays hidden behind
  the texture, so those two tokens still need the rasters regenerated to take
  visible effect — as `docs/THEMING.md` has always said. The type tokens
  (`ink`, `ink_deep`, `rule`, `display`, `body`) are visible immediately.

- **The PDF was not set in the theme's fonts.** `font_face_css()` returned a
  plain `str`, so the autoescaping template turned every `url("…")` into
  `url(&#34;…&#34;)`. HTML entities are not decoded inside a `<style>` element,
  which made each `@font-face` invalid — WeasyPrint silently dropped them all and
  fell back to whatever serif the build machine happened to have. The book still
  rendered at the right trim and page count, so nothing caught it; only the type
  was wrong, and it varied by machine. Introduced in 0.1.0 by the switch to
  `autoescape=True` (which correctly updated `inline()` and missed this one), so
  every PDF built by 0.1.0 and 0.2.0 is affected. The EPUB was never affected —
  pandoc embeds fonts through a separate path — so the two outputs of one book
  have been in different typefaces until now. Rebuild to get the intended design.

  `font_face_css()` now returns `Markup` and escapes its own input: a theme is
  untrusted data, so a family name can no longer close the CSS string or the
  `<style>` element. A new test builds the sample book, renders it, and asserts
  every family in `theme.yaml` is embedded in the PDF — the suite had no check on
  type at all, which is why this survived.

- The colophon pinned "produced by" to the top edge and the copyright to the
  bottom with a hollow of navy between them (`space-between` around an empty
  div). It is now one block centred on the sheet.

- A book with no `volume:` printed the bare word "Volume" on its cover, with
  nothing after it. The line is now omitted unless a volume is set, as the
  subtitle already was.

- The PDF outline listed every `### ingredient group` — "Filling", "Glaze" — as a
  navigable child of its recipe. Those are labels, not destinations; the outline
  now stops at recipe titles.

- Contents pages after the first used to run edge to edge. The index is the one
  page that flows across sheets, and element padding lands only on the first
  fragment's top and the last fragment's bottom — so every continuation sheet had
  its first entry jammed against the trim. The per-sheet breathing room now comes
  from padding on the page element with `box-decoration-break: clone`, which
  repeats the padding and the paper texture on every fragment. (The texture has
  to stay on the element: an `@page` background never paints the margin band, so
  a full-bleed sheet would print white edges.) The contents also loses its running
  footer, which was absolutely positioned against the fragmenting box and so
  landed on only one of its sheets.

- A recipe whose method overran its sheet lost **every** ingredient, not just
  the tail of the method. Unpinning the column row from the sheet height (an
  attempt to stop the divider drawing into blank paper beside short recipes) let
  the row grow to the method's full height; the row then fragmented and the
  whole ingredients column landed past the first sheet, where `overflow: hidden`
  discarded it. The row is pinned again, so both columns start at the top and
  only the tail of a long method is cut. The divider goes back to running the
  full sheet height beside a short recipe — cosmetic, and the real fix is to let
  a long recipe flow onto a second sheet, which the layout cannot yet do.

- `validate`'s page-count check assumed two pages for every recipe, so a book
  whose recipes carry no art reported a large, permanent delta. It now counts the
  pages each recipe actually takes, and says outright that the contents spans more
  than the one sheet it is budgeted in a long book — the delta used to send you
  hunting through NOTES sections for a cause that was never there.

- `validate`'s contact sheet for a long book (~145+ pages) used to be a single
  image taller than the ~16384px canvas dimension many viewers can open — it now
  paginates into `contact-sheet.png`, `contact-sheet-02.png`, … so every sheet
  stays openable.

- The bundled sample book had a direction step wrapped onto a second line, so
  `ladle theme preview` rendered it truncated mid-clause.

- `validate` no longer aborts on the very files it exists to report. A recipe
  with no front matter used to end the run with `error: list index out of range`,
  naming no file; an unclosed `---` block did the same. Both are now reported per
  file, and the remaining checks still run.

- `validate` without poppler installed used to die on a raw
  `[Errno 2] No such file or directory: 'pdfinfo'`, making its own "is poppler
  installed?" message unreachable. It now reports that check as failed and
  carries on to the EPUB check.

### Removed

- `cairosvg` and `numpy` are no longer runtime dependencies. Both existed only
  for `bake_assets.py`, which generated the theme's paper-grain rasters; that
  command was removed once the rasters were pre-baked and committed, but the two
  declarations (and `doctor`'s checks for them) were left behind. Neither is
  imported anywhere, so nothing changes at build time — SVG illustrations were
  already being rendered by WeasyPrint's own SVG support. Installs get smaller
  and `ladle doctor` stops failing over packages the tool never loads.

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
