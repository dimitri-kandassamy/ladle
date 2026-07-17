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
2. **Theme ecosystem** — finish Phase 0 (Jinja sandbox, `theme lint`,
   `theme preview`); more bundled themes; a **community gallery** in the
   static-site-generator mold. Safety model: anyone may build/use their own theme
   _at their own risk_ (path-based, no gate); **featured gallery themes must pass
   `ladle theme lint`** (schema + sandbox + font-license). The tool repo owns the
   safety machinery; the **gallery lives in its own repo**. No marketplace, no
   paid themes, no rev-share.
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
- **Phase 2 — Theme ecosystem.** Finish Phase 0 (sandbox/lint/preview) + the
  community-contribution path + `theme use/list/show` + `themes add/search`.
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
- **Self-publishing metadata is a nested `metadata:` block**; `contributors:` are
  `{name, role}`; accessibility `auto`.
- **Trim/page size stays theme-owned** (no per-book override); print bleed/safe
  zones are theme-authorable.

## Not doing (and why)

- **Theme marketplace / paid themes / revenue share** — the gallery is free and
  community-run, not a store.
- **AI theme generation** — out.
- **LLM / Ollama in ingestion** — the scraper is deterministic; no model.
- **Hosted SaaS/web-app builder as the focus** — possible someday, but the plan
  is local-CLI-only and depends on no cloud.
- **CMYK / PDF-X output + print-shop proof-copy testing** — the pro-print rabbit
  hole (partly beyond WeasyPrint). ladle stops at sellable RGB files.
- **Running the LLM/network in CI** — CI consumes only committed markdown.
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
