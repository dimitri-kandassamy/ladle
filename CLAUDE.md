# CLAUDE.md

## What ladle is

`ladle` builds art-directed cookbooks — a print-ready **PDF** (WeasyPrint) and an
epubcheck-clean **EPUB** (pandoc) — from a folder of markdown recipes driven by a
single `book.yaml`. Single-book, cwd-based model: a command operates on one book
(`--book PATH` or `./book.yaml`), and build artifacts land in `./build/`
(override with `$LADLE_BUILD`). Python 3.11+.

Note: the PyPI package is **`ladlebook`** (the name `ladle` was taken); the
command and the import package are both `ladle`.

## Commands

```sh
pip install -e '.[dev]'   # dev deps: pytest + ruff (pinned ==0.15.21)

make test     # python3 -m pytest  (src/ layout; pytest finds `ladle` via pyproject pythonpath)
make lint     # ruff check + ruff format --check, on src/ and tests/
make format   # ruff format in place (the canonical style)
make check    # lint + test — the fast CI gate

make build    # build PDF+EPUB (defaults BOOK=examples/the-ladle-kitchen/book.yaml)
make validate # schema + PDF structure + epubcheck + contact sheet
make doctor   # preflight: is pandoc/poppler/WeasyPrint/Java installed
make new-book NAME=pt   # scaffold ./pt/
```

Run the CLI directly from a checkout: `PYTHONPATH=src python3 -m ladle <cmd>`.

## Architecture

- **Entry:** `python -m ladle` → `ladle/__main__.py` → `cli.main`.
- **`cli.py`** — the `COMMANDS` registry (`Command(fn, help, book)`) is the single
  source of truth for both dispatch and top-level `--help`. `main` handles the
  top-level actions `-h/--help` and `-V/--version` (version only as the first
  token, matching git/cargo/pip), then dispatches to a command's `main(argv)`.
- **Commands:** `new` (`new_book.py`), `build` (`cli._build` → `build_html.render`
  → `make_pdf.render` → `make_epub.render`), `validate` (`validate.py`), `doctor`
  (`doctor.py` — toolchain preflight; `doctor --install` offers a confirm-first
  dependency install).
- **`config.py`** — path + book resolution. Two path roots: **package data**
  (`schema/`, `themes/`, resolves against the installed package) vs **user book
  content** (`recipes`/illustrations/intro, relative to the book.yaml's dir via
  `BookConfig.root`). `resolve_book_path`: `--book` › `./book.yaml`. Bad configs
  raise `ConfigError`/`NoBookError` (friendly messages, not tracebacks).
- **`ui.py`** — shared console. **All human output goes to stderr**; stdout is
  reserved/clean for piping. Color gating honors TTY, `NO_COLOR`, `TERM=dumb`, and
  `--color`/`--no-color`. Exit codes: `OK=0 ERROR=1 USAGE=2 NO_BOOK=3
  VALIDATION=4 INTERRUPTED=130`.

## Conventions

- **Conventional Commits** (`feat(cli): …`, `fix(…): …`, `refactor`, `docs`).
- **One PR per change**, branched off `main`.
- **No raw tracebacks to users:** raise `ConfigError`/`NoBookError` or
  `return ui.die(msg, code, hint=…)`; the top-level guard only re-raises under `-v`.
- ruff pinned `==0.15.21`, `line-length = 120`.

## Gotchas

- **Version is single-sourced** from `importlib.metadata` (`__init__.py`), so
  `--version` reflects the _installed_ metadata. After bumping `pyproject.toml`,
  run `pip install -e .` to refresh it (shows `0.0.0+dev` if never installed).
- **Releasing:** the tag `vX.Y.Z` must match `pyproject.toml`'s `version` or the
  `publish-pypi` job (`.github/workflows/build.yml`) fails. Creating the tag —
  `git push` a tag, or `gh release create` — triggers the OIDC PyPI publish, which
  is **irreversible** (PyPI versions can't be re-uploaded).
- **Tracked docs** — `README.md`, `CLAUDE.md`, `DESIGN.md`, `PLAN.md`,
  `CHANGELOG.md`, `docs/THEMING.md`: edits to these belong in the PR. Product
  scope/roadmap/decisions live in `PLAN.md`; the old local planning docs
  (SPEC/VISION/decisions/tasks/*) were superseded by it and archived under
  `.plan-archive/` (git-ignored).

## See also

- `PLAN.md` — product scope, roadmap, and locked decisions (start here for _why_ / _what's next_).
- `DESIGN.md` — architecture and the build stages in depth.
- `README.md` — user-facing install/usage.
