# ladle — product plan

> The one-pager: what ladle is, who it's for, what's next, and what it won't do.
> Companions: **README.md** (install/usage), **CLAUDE.md** (how to work the code),
> **DESIGN.md** (build architecture). This doc owns product scope + roadmap +
> decisions — the others link here, they don't restate it.

## What ladle is

ladle turns a folder of markdown recipes into a print-ready
**PDF** and a validated **EPUB** cookbook — art-directed, deterministic,
dependency-light, pure Python (no browser, no Node).

ladle is a **local-first, self-publishing toolkit for cookbooks**: a community
theme gallery, self-publishing metadata (dedication/ISBN/…), a deterministic
recipe scraper.

**Form constraint (permanent).** ladle is a **local CLI, forever**. A hosted
SaaS/web app is _not rejected_ but is explicitly **not the focus** now; nothing
in this plan depends on cloud. The job is to make the local CLI experience
insanely good at publishing recipes.

**North star.** A giftable, heirloom-quality cookbook worth printing, keeping,
giving away — and self-publishing/selling. Narrow = **aimed**, not small.

## Who it's for

The **tech-savvy cook**: comfortable with git + markdown + a CLI, who wants a
giftable book _and_ to self-publish/distribute it. This includes the tech-savvy
person making a book _for_ the non-technical people in their life (family, a
community) — the proxy author, and ladle's way of reaching those audiences
without a separate authoring door. **Not a recipe manager.**

## Workstreams (in scope)

1. **Core** (done) — `build`/`new`/`validate`/`doctor`, themes, the
   `book.yaml` + recipe-markdown contracts, PDF + EPUB output.
2. **Theme ecosystem** — Phase 0 done (Jinja sandbox, `theme lint`,
   `theme preview`); next: more bundled themes; **overlay override** (a book tweaks
   one template/CSS file/block without forking — the MkDocs `custom_dir` + Jinja
   `{% block %}` model, the one thing every SSG has that ladle lacks); enforce the
   `theme.yaml` `ladle` **version-compat range** at load (Hugo `min_version` model,
   already declared but unenforced); a **community gallery** in the
   static-site-generator mold. Safety model: anyone may build/use their own theme
   _at their own risk_ (path-based, no gate); **featured gallery themes must pass
   `ladle theme lint`** (schema + sandbox + font-license). The tool repo owns the
   safety machinery; the **gallery lives in its own repo** — a git-based theme +
   static index, _not_ a language package manager (a ladle theme is a data bundle,
   not importable code; validated against Hugo/Jekyll/MkDocs/Docusaurus/Zola).
   No marketplace, no paid themes, no rev-share.
3. **Self-publishing depth** — front/back matter (dedication, foreword,
   acknowledgments, about); book-level `contributors: {name, role}`; a nested
   `metadata:` block (ISBN/identifier, description, publisher, date, subjects);
   accessibility `auto`. Emits Dublin Core in the EPUB + PDF document metadata.
   **Distribute = sellable files only** (ISBN-stamped RGB PDF + EPUB you upload
   yourself); make the `@page`/theme model **print-aware** (bleed + safe zones,
   trim-owned) so a KDP/Lulu **preset** (cover spread + gutter + crop marks) stays
   reachable someday.
4. **Ingestion (scraper, no AI)** — `ladle scoop <url>` → deterministic extract
   (schema.org/Recipe JSON-LD, readable-text fallback) → `recipes/*.md`. CI-safe,
   LLM-free — no Ollama, no model.
5. **Presence & distribution** — a **branded landing page + docs + theme gallery
   as one site** in a **dedicated web repo** (doc framework + marketing landing),
   separate from the pure-Python tool repo; the README stays the canonical,
   in-repo quickstart. Visual identity (logo, voice); easy install via **Homebrew
   tap** (+ pipx/Docker) to close the system-deps gap.

## Roadmap — one active focus at a time

**Launch is the goal, and "public" ≠ "launched."** ladle is already on GitHub/PyPI
(availability); launching is the deliberate distribution moment (a Show HN /
lobste.rs post), which only pays off once the funnel top exists to catch it. So
presence + distribution come first — they _are_ the launch prerequisites.

- **Phase 1 — Presence & distribution (launch prep) · NEXT.** Brand/identity →
  landing + docs site → Homebrew tap + one-step install → seed the gallery with a
  few themes to show range → audit the README's install claim for accuracy → **the
  launch post.** _First step (recommended): brand/identity + a landing skeleton,
  since it gates the visual work; Homebrew/install runs as a parallel track._
- **Phase 2 — Theme ecosystem.** Phase 0 done (sandbox/lint/preview). Next,
  the customization model — five moves, drawn from how Hugo/MkDocs/Zola implement
  themes (three engines that converged on the same override architecture):
  1. **Overlay override (file-level)** — a book's `theme_overrides/` dir shadows
     theme templates/CSS by relative path via a layered Jinja `FileSystemLoader`,
     first match wins (MkDocs `custom_dir`). Small change, highest leverage; stays
     inside the sandbox.
  2. **Block contract (partial override)** — refactor the bundled theme into a
     `base.html.j2` + named blocks (`cover`/`contents`/`recipe_card`/…) so a book
     overrides one block via `{% extends %}` without copying the file; publish the
     block set as a stable contract, marking Safe vs internal blocks (the
     Docusaurus swizzle-tier idea).
  3. **Theme `params` namespace** — generalize the palette/fonts token-merge to
     arbitrary theme-declared knobs with defaults, book-overridable (MkDocs
     `config.theme.*` / Hugo `.Site.Params` / Zola `[extra]`). The substrate for
     parametric themes (§gallery).
  4. **Theme-local preview content** — `theme preview` prefers a theme's own
     `sample/` if present, else the canonical sample (Zola's "a theme is a site":
     the author frames it with flattering content).
  5. **Enforce the `theme.yaml` `ladle` version-compat range at load** (Hugo/Zola
     `min_version`) — already declared in the schema, currently unenforced.

  Then: more bundled themes + the community-contribution path + `theme
  use/list/show` + `themes add/search`.
- **Phase 3 — Self-publishing depth.** Front/back matter, contributors,
  `metadata:`/ISBN, accessibility, print-aware `@page`.
- **Phase 4 — Ingestion scraper.** `ladle scoop <url>`, deterministic, CI-safe.

**Opportunistic (ungated, pick anytime):** builder polish — `-C/--chdir`, `-` as
stdin, `build -o/--output` + `--drafts`, spinners; infra — upward `book.yaml`
search (stop at `.git`), hatch-vcs (git tag → version).

## Locked decisions

- **Deterministic, dependency-light builder; output stays PDF + EPUB** (not
  EPUB-only — the print PDF is the differentiator).
- **Local CLI is the permanent form; SaaS deferred, not rejected.**
- **YAML config + JSON-Schema contracts + argparse**; adopt clig.dev conventions,
  not Typer/pydantic/TOML for their own sake.
- **Ingestion is a deterministic scraper — no LLM at all.** CI never runs
  network/LLM.
- **`book.yaml` + `theme.yaml` validated by strict schemas at load** (typos fail
  fast, not silently).
- **Themes distribute git-based + a static gallery index — not via a language
  package manager** (PyPI/npm/gems). A theme is a data bundle (Jinja, CSS, fonts,
  rasters), not importable code, so wrapping it as a package buys nothing; the
  Hugo/Zola model fits. Native `themes`/`theme` commands, not host-PM delegation.
- **Theme templates are untrusted; fonts are embedded/redistributed** — hence the
  `SandboxedEnvironment` + per-font-license `theme lint` gate (a differentiator vs
  SSGs, which serve web fonts and leave licensing to the site author).
- **Self-publishing metadata is a nested `metadata:` block**; `contributors:` are
  `{name, role}`; accessibility `auto`.
- **Trim/page size stays theme-owned** (no per-book override); print bleed/safe
  zones are theme-authorable.
- **Recipe bodies are markdown under fixed section headings — rendered, not
  grammar-parsed.** A recipe is front matter plus markdown under `## HEADING`s.
  ladle splits on the headings and hands each section's body to its own
  dependency-light block renderer (the one that already renders prose); it does
  **not** parse steps/ingredients into a bespoke line grammar. One parse produces
  the HTML both outputs consume (WeasyPrint for PDF, pandoc `--from html` for
  EPUB), so the two can't diverge. Markdown freedom is "we don't block it": a
  documented, tested subset (inline links/bold/italic, `-`/`*` and `1.` lists,
  `###` sub-headings) is supported and styled; anything else renders at the
  author's risk. Consequences of this model:
  - **Section headings are fixed canonical English keys** (`## INGREDIENTS`,
    `## METHOD`, `## NOTES`); the reader sees localized text via the existing
    `labels:` map. This decouples file structure from display language — so
    there is **no native-language heading alias map**.
  - **An unrecognized heading renders as a generic titled block and warns** —
    content is never silently dropped, and no per-theme "slot" contract is
    needed.
  - **A missing mandatory section (ingredients/method) warns, it does not block
    the build** (a drink or a cheese board is legitimate); `validate --strict`
    can escalate it for CI.
  - **`##` is reserved as the section boundary**; `###` and deeper are free
    inside a section. Documented, no new syntax.

## Not doing (and why)

- **Theme marketplace / paid themes / revenue share** — the gallery is free and
  community-run, not a store (aligned with Hugo/Jekyll/Pelican/Zola; Astro's paid
  marketplace is the outlier and a JS-ecosystem play, not a print-tool one).
- **AI theme generation** — out.
- **LLM / Ollama in ingestion** — the scraper is deterministic; no model.
- **Hosted SaaS/web-app builder as the focus** — possible someday, but the plan
  is local-CLI-only and depends on no cloud.
- **CMYK / PDF-X output + print-shop proof-copy testing** — the pro-print rabbit
  hole (partly beyond WeasyPrint). ladle stops at sellable RGB files.
- **Running the LLM/network in CI** — CI consumes only committed markdown.
- **A Hugo-style template lookup-order engine** — ladle has a fixed two-template
  contract (print + epub); a layered loader gives overrides without the lookup
  machinery Hugo needs for thousands of heterogeneous pages.
- **A Sass/asset pipeline (Hugo Pipes, Zola Sass)** — ladle stays dependency-light
  and hands print CSS straight to WeasyPrint; no libsass/fingerprinting unless
  theme authors actually ask.
- Also out: framework churn (TOML/pydantic/Typer for their own sake);
  `extract-template` (distill a theme from an EPUB); photos/OCR/vision ingestion;
  unit conversion & nutrition; full ONIX/price trade feed; series/collection
  metadata (`volume` covers the common case).

## Open questions

- **Retention metric** — what we optimize after launch: books built per user? a
  2nd book within N days?
- **Brand** — name stays "ladle" (PyPI `ladlebook`)? logo + voice direction (the
  old "CLI personality" idea folds in here).
- **Phase-1 first step** — confirm brand-first vs install-first when Phase 1 starts.
