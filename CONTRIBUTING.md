# Contributing to ladle

Thanks for helping improve the tool! This guide is about contributing to
**`ladle` itself** — code, themes, and docs. If instead you want to add a
**recipe** to the example cookbook, see
[`examples/the-ladle-kitchen/CONTRIBUTING.md`](examples/the-ladle-kitchen/CONTRIBUTING.md).

## Dev setup

```sh
git clone https://github.com/dimitri-kandassamy/ladle && cd ladle
pip install -e '.[dev]'    # the tool + test/lint tooling (pytest, ruff)
ladle doctor               # verify pandoc / poppler / WeasyPrint / Java
make all                   # build the example book (examples/the-ladle-kitchen)
make validate              # schema + PDF structure + epubcheck + contact sheet
```

Run the unit tests and linter before opening a PR (CI runs both):

```sh
pytest                     # unit tests (tests/test_*.py)
ruff check src tests       # lint (style, dead code, import order)
```

Unit tests cover the pure parsing/config logic across Python 3.11–3.13; the
example-book build (`make all && make validate`) is the end-to-end regression
guard. Both run in CI.

`make` runs the package straight from `src/` (`PYTHONPATH=src python3 -m ladle`),
so no install is needed to iterate. `make all BOOK=path/to/book.yaml` builds any
book. There is also a torture-test fixture that exercises the tricky cases
(quoted titles, accents, missing optional fields, long notes):

```sh
make all BOOK=tests/fixtures/torture-book/book.yaml
make validate BOOK=tests/fixtures/torture-book/book.yaml
```

## Repository layout

| Path | What |
| --- | --- |
| `src/ladle/` | the package — `cli.py`, `config.py`, and the build/validate modules |
| `src/ladle/schema/` | the recipe JSON Schema |
| `src/ladle/themes/default/` | the built-in theme (manifest + templates + css + fonts + patterns) |
| `examples/the-ladle-kitchen/` | the reference example book |
| `tests/fixtures/torture-book/` | CI edge-case fixture |
| `Makefile` | thin wrapper over the `ladle` CLI |
| `tests/test_*.py` | unit tests (pytest) |
| `.github/workflows/build.yml` | lint, unit tests, build, validate (+ release) |

## Making a change

1. Branch off `main`.
2. Keep the example build green: `make all && make validate` should still report
   the same page count and a clean epubcheck. The example book is the
   regression guard — if a change alters its output, that should be intentional.
3. Match the surrounding code: type hints, module docstrings explaining *why*,
   `main(argv=None)` entry points wired through `cli.py`.
4. Update docs when you change behaviour (README, and `docs/THEMING.md` for
   theme-facing changes).
5. Open a pull request. CI must pass.

## Adding a theme

Themes are the intended extension point — see
[docs/THEMING.md](docs/THEMING.md) for the manifest format and authoring
workflow. A new built-in theme is a directory under `src/ladle/themes/`; a
book-local theme lives in the book and is selected by path.

## Architecture

See [DESIGN.md](DESIGN.md) for the parse → render → build pipeline and the
design rationale.

## Licensing

Code contributions are licensed **Apache-2.0** (see [`LICENSE`](LICENSE)); the
example book's content is **CC BY-SA 4.0** (see [`LICENSE-CONTENT`](LICENSE-CONTENT)).
This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). Be kind.
