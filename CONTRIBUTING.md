# Contributing

Thank you for adding to the cookbook! Contributions are recipes (most common),
illustrations, and improvements to the build.

## Add a recipe

1. **Create the file.** Name it `recipes/<slug>.md` where `<slug>` is lowercase,
   hyphenated, ASCII (e.g. `lemon-olive-oil-cake.md`).
2. **Write the front matter and body** following the format in the
   [README](README.md#recipe-format). Required fields: `title`, `category`,
   `servings`, `credits`.
3. **Pick a category:** `Savory`, `Desserts`, or `Beverages`.
4. **Credit the source** in `credits` — a person, a book, or a URL. If you adapted a
   published recipe, also set `attribution: "Based on a recipe by …"`.
5. **Build and check:**
   ```sh
   make all && make validate
   open build/contact-sheet.png
   ```
6. **Open a pull request.** CI will validate the schema, lint markdown, and rebuild.

### Style conventions

- One ingredient per `- ` line. Group with `### Group` headings when a recipe has parts
  (e.g. *Cake* / *Frosting*).
- Numbered `## DIRECTIONS` steps, imperative voice.
- Units: metric preferred (`g`, `ml`, `tbsp`, `tsp`). Temperatures as `180°C` (no space).
- Keep ingredients and steps concise — the print layout favours short lines.
- Want the full **story page** treatment? Add a `story:` paragraph and, optionally,
  `author: {name, org}` and a `headshot:` image. Otherwise you get a clean compact opener.

## Add or change illustrations

Each recipe ships with an auto-generated SVG placeholder. To contribute real art:

1. Run `python3 tools/illustration_prompts.py` and open [`ILLUSTRATIONS.md`](ILLUSTRATIONS.md).
2. Generate your recipe's image from the listed prompt at the recommended size (any image
   model; the prompts are tuned for *nano banana* / Gemini 2.5 Flash Image).
3. Save it as `assets/illustrations/recipes/<slug>.png` (transparent **PNG** or WebP; not
   JPEG). The build prefers it over the placeholder automatically — no front-matter change.

Keep to the cookbook's visual language (loose watercolour-and-ink, **transparent
background**, plate-centred, soft cast shadow, lots of negative space) so each image drops
onto the cream page cleanly. Only submit art you have the right to share; AI-generated
images are welcome.

## Licensing of contributions

By contributing you agree that:

- **content** (your recipe text, story, images) is licensed **CC BY-SA 4.0**, and
- **code** changes are licensed **Apache-2.0**.

Only submit content you have the right to share. Don't paste copyrighted recipe text or
photos; write the method in your own words and credit the source.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be kind.
