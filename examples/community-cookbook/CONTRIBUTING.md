# Contributing a recipe to The Community Cookbook

This is the example book that ships with [`ladle`](../../README.md). Paths below
are relative to this directory (`examples/community-cookbook/`). To contribute a
recipe:

1. **Create the file.** Name it `recipes/<slug>.md` where `<slug>` is lowercase,
   hyphenated, ASCII (e.g. `lemon-olive-oil-cake.md`).
2. **Write the front matter and body** following the format in the
   [README](../../README.md#recipe-format). Required: `title`, `category`.
   `servings`, `credits`, and `page` are optional — include them when known,
   omit them when the source gives no yield, named source, or page number.
3. **Pick a category:** `Savory`, `Desserts`, or `Beverages`.
4. **Credit the source** in `credits` when you have one — a person, a book, or a
   URL. If you adapted a published recipe, also set
   `attribution: "Based on a recipe by …"`.
5. **Build and check** (from the repo root):

   ```sh
   make all && make validate            # this example is the default build target
   open build/contact-sheet.png
   ```

   Or explicitly: `ladle build --book examples/community-cookbook/book.yaml`.
6. **Open a pull request.** CI lints markdown, validates the schema, and rebuilds.

## Style conventions

- One ingredient per list item. Group with `### Group` headings when a recipe
  has parts (e.g. *Cake* / *Frosting*).
- Numbered `## DIRECTIONS` steps, imperative voice.
- Units: metric preferred (`g`, `ml`, `tbsp`, `tsp`). Temperatures as `180°C`.
- Keep ingredients and steps concise — the print layout favours short lines.
- Want the full **story page** treatment? Add a `story:` paragraph and,
  optionally, `author: {name, org}` and a `headshot:`. Otherwise you get a clean
  compact opener.

## Illustrations

Each recipe ships with an auto-generated SVG placeholder. To contribute real art,
generate your recipe's image in the theme's locked style (see
[DESIGN.md](../../DESIGN.md#illustrations)), export ~1500 px wide on a
**transparent background**, and save it as
`assets/illustrations/recipes/<slug>.png` (transparent **PNG** or WebP; not
JPEG). The build prefers it over the placeholder automatically — no front-matter
change. Only submit art you have the right to share; AI-generated images welcome.

## Licensing of contributions

By contributing you agree that **content** (recipe text, story, images) is
licensed **CC BY-SA 4.0**. Only submit content you have the right to share —
write the method in your own words and credit the source; don't paste
copyrighted recipe text or photos.

This project follows the [Contributor Covenant](../../CODE_OF_CONDUCT.md). Be kind.
