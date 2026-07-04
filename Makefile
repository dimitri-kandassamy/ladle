# ladle — build orchestration (a thin wrapper over the `ladle` CLI).
#
#   make all          build PDF + EPUB
#   make pdf          art-directed PDF (WeasyPrint)
#   make epub         reflowable EPUB (pandoc)
#   make html         render print + epub HTML only
#   make illustrations  (re)generate the SVG placeholder line-art
#   make assets       re-bake the default theme's raster brand assets
#   make validate     schema + structural + epubcheck + contact sheet
#   make doctor       preflight-check pandoc/poppler/WeasyPrint/Java are installed
#   make new-book NAME=x   scaffold a new book under books/x/
#   make clean
#
# Add BOOK=path/to/book.yaml to build a book other than ./book.yaml, e.g.
#   make all BOOK=examples/community-cookbook/book.yaml
#
# This runs the package straight from src/ — no install needed. After
# `pip install -e .` (or `pip install ladle`), the same verbs are available as
# `ladle build`, `ladle validate`, … from any book's directory.

LADLE := PYTHONPATH=src python3 -m ladle
BUILD := build

BOOK      ?=
BOOK_FLAG := $(if $(BOOK),--book $(BOOK),)

.PHONY: all pdf epub html illustrations assets validate doctor new-book clean

all: pdf epub

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
