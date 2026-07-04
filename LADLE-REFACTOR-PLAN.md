# Refactor plan: turn this repo into `ladle`, a book-building tool

**Status file for resuming across sessions.** Last updated: 2026-07-04.

## Goal (user's words)

This repo currently *is* a book (The Community Cookbook). Flip it so its **main
purpose is the tooling to create books** — an open-source project that builds a
book in multiple formats (PDF + EPUB) from markdown. The current book/recipes
stay as an **example**, not the point of the repo.

## Locked decisions

The user chose the maximal-ambition path on every axis:

| Decision | Choice |
| --- | --- |
| Identity | **Split into two repos**: a tool repo (this one) + a separate flagship book repo that consumes the published package. |
| Example book location | **Move to `examples/community-cookbook/`**; repo root becomes tool-only. |
| Distribution | **Full productization**: installable CLI + PyPI + starter template. |
| Theming | **Pluggable themes** (not a single baked-in look). |
| Name | **`ladle`** — one token for everything: PyPI dist `ladle`, import `ladle`, CLI command `ladle`, GitHub repo `ladle`. Confirmed free on PyPI. (Rejected: `roux` taken on PyPI; `cookbook-press`/`cookbook` command felt generic + 3-name spread.) |

## Context: what existed before this refactor

- This IS the upstream `community-cookbook` repo. The 5 most recent commits
  (before this work) already implemented the RETROSPECTIVE.md recommendations:
  multi-book config loader (`bookconfig.py`), `make new-book`, `make doctor`,
  page-count-as-diagnostic, torture-test fixture + CI, label externalization,
  escaping/schema fixes. So **"book" was already a first-class config concept**
  before we started; this refactor is about repositioning + productizing.
- `RETROSPECTIVE.md` and `CHANGES-FROM-UPSTREAM.md` (untracked, at repo root)
  were carried over from a `family-cookbook` vendoring context. Phase 0 decides
  their fate (fold rationale into `docs/`, drop CHANGES-FROM-UPSTREAM.md).

## Phased plan

- **Phase 0 — Name & housekeeping.** ✅ Name locked (`ladle`). ⬜ Decide fate of
  the two carried-over docs (fold durable rationale into `docs/`, drop
  `CHANGES-FROM-UPSTREAM.md` — it describes a vendored copy that won't exist
  post-split). NOT yet done.
- **Phase 1 — Repackage as installable CLI.** ✅ DONE + verified (details below).
- **Phase 2 — Move the demo book out of root** → `examples/community-cookbook/`
  (its `book.yaml`, `recipes/`, `content/introduction.md`, and generated
  `assets/illustrations/recipes/*.svg`). Make the CLI default to the example
  (or require `--book`). Root becomes tool-only. Decide: hard-require `--book`
  vs friendly default to the example (leaning: friendly default so `ladle build`
  does something out of the box).
- **Phase 3 — Pluggable themes.** The seam is already in place: assets live in
  `src/ladle/themes/default/` and `config.BookConfig.theme_dir` resolves
  `theme:` as a bundled name OR a book-local path. Remaining: add a
  `theme.yaml` manifest (palette/font defaults), let a book select/author a
  theme, `docs/THEMING.md`, keep `default` pixel-identical (regression-guard via
  contact sheet). Largest design refactor.
- **Phase 4 — CLI ergonomics & starter template.** Generalize `ladle new` into
  the cookiecutter path (scaffold a standalone book that builds against the
  *installed* package). Publish a `ladle-book-template` starter repo.
- **Phase 5 — CI & release for the tool.** Rework `.github/workflows/`: a
  **test** job (lint + build+validate the example book AND the torture fixture,
  as a matrix) and a **release** job (build sdist/wheel, publish to PyPI on
  `v*` tags via `pypa/gh-action-pypi-publish`). Version the *tool* (semver)
  separately from book *editions* (edition/rolling-release logic moves to the
  book repo).
- **Phase 6 — Documentation split.** README becomes a *tool* README (install →
  `ladle new` → build → deploy; cookbook demoted to "see `examples/`").
  Split CONTRIBUTING: tool code vs. recipe contribution (ships with
  example/starter). DESIGN.md refocused on theme-authoring + architecture.
- **Phase 7 — Spin out the flagship book repo.** New repo = current recipes +
  intro + `book.yaml`, `pip install ladle`, own CI building/releasing PDF+EPUB
  editions + Pages. Prepare its contents here; user runs the actual repo
  creation/push.

### Sequencing notes
Phases 1→2→3 are the core; do each as a separate commit keeping `make all`
green (verify with build + contact-sheet after each). Phase 3 is riskiest —
land 1–2 first so structure is stable before touching design plumbing.
Phases 4–7 are largely additive/docs.

## Task tracking

Legend: ✅ done · 🔟 in progress · ⬜ todo

- ✅ Establish green baseline (11 recipes, **28-page** PDF, epubcheck pass)
- ✅ **Phase 1: package skeleton** — `src/ladle/` created, tools moved via `git mv`
- ✅ Phase 1: `config.py` — package/theme/build path resolution (was `bookconfig.py`)
- ✅ Phase 1: relocate design assets → `src/ladle/themes/default/` (css/fonts/patterns/templates)
- ✅ Phase 1: relocate `schema/` → `src/ladle/schema/`
- ✅ Phase 1: rewire all 8 tool modules (imports `from . import config`, theme-driven paths, `main(argv=None)`)
- ✅ Phase 1: port `make_epub.sh` → `src/ladle/make_epub.py`
- ✅ Phase 1: `cli.py` + `__main__.py` + `__init__.py` (`ladle build|html|pdf|epub|illustrations|assets|validate|doctor|new`)
- ✅ Phase 1: `pyproject.toml` (`ladle` dist, console script, bundled data)
- ✅ Phase 1: rewire `Makefile` to `PYTHONPATH=src python3 -m ladle`
- ✅ Phase 1: verify build == baseline; wheel builds w/ data + entry point; torture book builds via `--book`
- ✅ **Phase 1: COMMITTED** — `2d14743` (code) + `fbf0746` (this plan)
- ✅ Phase 0: docs decision — **user: RETROSPECTIVE.md + CHANGES-FROM-UPSTREAM.md must NOT be committed**; they stay as local untracked working notes. (Do not fold into `docs/`; do not `git add` them.)
- ✅ Phase 2: move demo book → `examples/community-cookbook/`, root tool-only, Makefile `BOOK` defaults to example — committed `81cccdf`. Verified: `make all && make validate` (no BOOK) → 11 recipes, 28 pages, epubcheck pass.
- 🔟 Phase 3: pluggable themes (`theme.yaml` manifest, THEMING.md) — IN PROGRESS
- ⬜ Phase 4: `ladle new` starter path + template repo
- ⬜ Phase 5: CI test/release matrix + PyPI publish workflow
  - ✅ (partial) CI invocations updated to `pip install -e .` + `ladle … --book …`, committed `98f4803` (verified in a fresh venv). REMAINING: release/PyPI-publish job on `v*` tags, tool-vs-edition versioning, matrix.
- ⬜ Phase 6: docs split (README/CONTRIBUTING/DESIGN) — NOTE: README/DESIGN.md still reference old `tools/`, `recipes/`, root `book.yaml` paths; stale until this phase.
- ⬜ Phase 7: spin out flagship book repo

## Current git state (IMPORTANT for resuming)

- Branch: `feat/changes-after-review` (NOT main). Commits so far:
  - `2d14743` refactor(tools): repackage as installable 'ladle' CLI (Phase 1)
  - `fbf0746` docs: add ladle refactor plan + task tracking
  - `81cccdf` refactor: move demo book to examples/, root tool-only (Phase 2)
  - `98f4803` ci: drive builds via installed 'ladle' CLI + example book path
- `RETROSPECTIVE.md` + `CHANGES-FROM-UPSTREAM.md` are permanently **untracked**
  by the user's instruction — NEVER `git add` them.
- In progress: Phase 3 (pluggable themes). Nothing uncommitted expected at the
  start of a fresh session unless Phase 3 work is mid-flight.

## Key technical context / decisions (so a cold session doesn't re-derive)

- **Two path roots.** Tool/theme data resolves against `config.PACKAGE_ROOT`
  (`src/ladle/`), so it works in a checkout and in site-packages. Book content
  (`recipes_dir`/`illustrations_dir`/`introduction`) resolves against each
  book's own `book.yaml` dir (`BookConfig.root`). Build output = `./build`
  (cwd-relative, `$LADLE_BUILD` override).
- **EPUB asset paths** are expressed relative to **cwd** in `build_html.py`
  (`asset_url(absolute=False)` uses `Path.cwd()`), because `make_epub.py` runs
  pandoc from cwd with `--resource-path ".:<build>"`. Theme fonts + `epub.css`
  are passed to pandoc as **absolute** paths from the theme dir.
- **Print CSS → patterns** relative link: `print.css` references
  `url(../illustrations/patterns/…)`, so `css/` and `illustrations/patterns/`
  MUST remain siblings inside a theme dir. Preserved in `themes/default/`.
- **epubcheck jar**: `config.epubcheck_jar()` → `tools/epubcheck/epubcheck.jar`
  (cwd) with `$EPUBCHECK_JAR` override. `tools/epubcheck/` is gitignored
  (downloaded). `validate` falls back to a structural check without Java/jar.
- **`theme_dir` resolution** (`config.py`): bare name → `PACKAGE_ROOT/themes/<name>`;
  path with a separator or absolute → book-relative/absolute. This is the
  Phase 3 hook, already working.
- CI (`.github/workflows/build.yml`) still calls the OLD `python3 tools/…`
  invocations — **Phase 5 must update it** to `ladle …` (or `PYTHONPATH=src
  python -m ladle …`). Not yet touched; CI would break on the old paths.

## How to build / verify (from repo root)

```sh
make all           # PYTHONPATH=src python3 -m ladle html/pdf/epub
make validate      # expect: 11 recipes, 28-page PDF, epubcheck pass, contact sheet
# multi-book:
make all BOOK=tests/fixtures/torture-book/book.yaml
# wheel packaging sanity:
pip wheel . --no-deps -w /tmp/wh   # bundles themes+schema, entry point ladle=ladle.cli:main
```

Local env has all deps (weasyprint, pandoc, poppler, java, epubcheck jar), so
full build+validate is verifiable here.

## Open questions to confirm with user

- Phase 2: hard-require `--book` vs. default `ladle build` to the example book?
- Phase 0: confirm dropping `CHANGES-FROM-UPSTREAM.md` and folding
  `RETROSPECTIVE.md` rationale into `docs/`.
- Phase 7: user will create/push the separate flagship book repo (we prepare
  contents here).
