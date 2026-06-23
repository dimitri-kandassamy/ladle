# The Community Cookbook — build orchestration.
#
#   make all          build PDF + EPUB
#   make pdf          art-directed PDF (WeasyPrint)
#   make epub         reflowable EPUB (pandoc) + epubcheck
#   make illustrations  (re)generate the SVG placeholder line-art
#   make assets       re-bake the raster brand assets (paper grain + patterns)
#   make validate     schema + structural + epubcheck + contact sheet
#   make clean

PY    := python3
BUILD := build

.PHONY: all pdf epub html illustrations assets validate clean

all: pdf epub

# On-brand SVG placeholder art (patterns + per-recipe spots).
illustrations:
	$(PY) tools/gen_illustrations.py

# Raster brand assets the PDF consumes (cream/navy paper grain, line-art PNGs).
assets: illustrations
	$(PY) tools/bake_assets.py

# Builds both build/cookbook.html (print) and build/epub.html (semantic).
html:
	$(PY) tools/build_html.py

pdf: html
	$(PY) tools/make_pdf.py

epub: html
	bash tools/make_epub.sh

validate:
	$(PY) tools/validate.py

clean:
	rm -rf $(BUILD)/cookbook.html $(BUILD)/epub.html $(BUILD)/cookbook.pdf \
	       $(BUILD)/cookbook.epub $(BUILD)/contact-sheet.png $(BUILD)/pdf_png
