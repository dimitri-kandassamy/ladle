# The Community Cookbook — build orchestration.
#
#   make all          build PDF + EPUB
#   make pdf          art-directed PDF (WeasyPrint)
#   make epub         reflowable EPUB (pandoc) + epubcheck
#   make illustrations  (re)generate the SVG placeholder line-art
#   make assets       re-bake the raster brand assets (paper grain + patterns)
#   make validate     schema + structural + epubcheck + contact sheet
#   make doctor       preflight-check pandoc/poppler/WeasyPrint/Java are installed
#   make new-book NAME=x   scaffold a new book under books/x/
#   make clean
#
# Add BOOK=path/to/book.yaml to any target to build a book other than the
# repo-root default, e.g. `make all BOOK=books/pt/book.yaml`.

PY    := python3
BUILD := build

# BOOK=path/to/book.yaml builds a book other than the repo-root default,
# e.g. `make all BOOK=books/pt/book.yaml`. Empty by default, which every
# tool interprets as "use the repo-root book.yaml" — zero-flag behavior is
# unchanged.
BOOK      ?=
BOOK_FLAG := $(if $(BOOK),--book $(BOOK),)

.PHONY: all pdf epub html illustrations assets validate doctor new-book clean

all: pdf epub

# On-brand SVG placeholder art (patterns + per-recipe spots).
illustrations:
	$(PY) tools/gen_illustrations.py $(BOOK_FLAG)

# Raster brand assets the PDF consumes (cream/navy paper grain, line-art PNGs).
assets: illustrations
	$(PY) tools/bake_assets.py

# Builds both build/cookbook.html (print) and build/epub.html (semantic).
html:
	$(PY) tools/build_html.py $(BOOK_FLAG)

pdf: html
	$(PY) tools/make_pdf.py

epub: html
	bash tools/make_epub.sh $(BOOK_FLAG)

validate:
	$(PY) tools/validate.py $(BOOK_FLAG)

# Preflight: check pandoc/poppler/WeasyPrint/Java are installed before a build.
doctor:
	$(PY) tools/doctor.py

# Scaffold a new book: `make new-book NAME=pt`.
new-book:
	$(PY) tools/new_book.py $(if $(NAME),--name $(NAME),)

clean:
	rm -rf $(BUILD)/cookbook.html $(BUILD)/epub.html $(BUILD)/cookbook.pdf \
	       $(BUILD)/cookbook.epub $(BUILD)/contact-sheet.png $(BUILD)/pdf_png
