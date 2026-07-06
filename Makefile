# ladle — build orchestration (a thin wrapper over the `ladle` CLI).
#
#   make all          build PDF + EPUB
#   make pdf          art-directed PDF (WeasyPrint)
#   make epub         reflowable EPUB (pandoc)
#   make html         render print + epub HTML only
#   make illustrations  (re)generate the SVG placeholder line-art
#   make assets       re-bake the default theme's raster brand assets
#   make validate     schema + structural + epubcheck + contact sheet
#   make test         run the unit tests (pytest)
#   make lint         run ruff over src/ and tests/
#   make check        lint + test (the fast, no-toolchain CI gate)
#   make doctor       preflight-check pandoc/poppler/WeasyPrint/Java are installed
#   make new-book NAME=x   scaffold a new book under books/x/
#   make clean
#
# `make all` builds the bundled example book (examples/the-ladle-kitchen).
# Override BOOK to build another book, e.g. `make all BOOK=books/pt/book.yaml`.
#
# This runs the package straight from src/ — no install needed. After
# `pip install -e .` (or `pip install ladle`), the same verbs are available as
# `ladle build`, `ladle validate`, … from any book's directory.

LADLE := PYTHONPATH=src python3 -m ladle
BUILD := build

BOOK      ?= examples/the-ladle-kitchen/book.yaml
BOOK_FLAG := $(if $(BOOK),--book $(BOOK),)

.PHONY: all pdf epub html illustrations assets validate test lint check doctor new-book clean

all: pdf epub

# Unit tests + lint — the fast CI gate, no book toolchain required.
# pytest resolves `ladle` from src/ via pyproject's pythonpath setting.
test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests

check: lint test

# On-brand SVG placeholder art (patterns + per-recipe spots).
illustrations:
	$(LADLE) illustrations $(BOOK_FLAG)

# Raster brand assets the PDF consumes (cream/navy paper grain, line-art PNGs).
assets: illustrations
	$(LADLE) assets

# Builds both build/cookbook.html (print) and build/epub.html (semantic).
html:
	$(LADLE) html $(BOOK_FLAG)

pdf: html
	$(LADLE) pdf $(BOOK_FLAG)

epub: html
	$(LADLE) epub $(BOOK_FLAG)

validate:
	$(LADLE) validate $(BOOK_FLAG)

# Preflight: check pandoc/poppler/WeasyPrint/Java are installed before a build.
doctor:
	$(LADLE) doctor

# Scaffold a new book: `make new-book NAME=pt`.
new-book:
	$(LADLE) new $(if $(NAME),--name $(NAME),)

clean:
	rm -rf $(BUILD)/cookbook.html $(BUILD)/epub.html $(BUILD)/cookbook.pdf \
	       $(BUILD)/cookbook.epub $(BUILD)/contact-sheet.png $(BUILD)/pdf_png
