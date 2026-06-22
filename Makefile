# The Community Cookbook — build orchestration.
#
#   make all         build PDF + EPUB
#   make pdf          art-directed PDF (Paged.js + Chrome)
#   make epub         reflowable EPUB (pandoc) + epubcheck
#   make illustrations  (re)generate the SVG placeholder art
#   make prompts      regenerate ILLUSTRATIONS.md (prompts + sizes for real artwork)
#   make paper        re-bake the cream paper-grain texture (needs Chrome)
#   make validate     schema + structural + epubcheck + contact sheet
#   make migrate      one-off: import recipes from the legacy heading-based repo
#   make clean

PY   := python3
NODE := node
BUILD := build

.PHONY: all pdf epub html illustrations prompts paper validate migrate clean

all: pdf epub

illustrations:
	$(PY) tools/gen_illustrations.py

# Regenerate ILLUSTRATIONS.md (prompts + sizes for hand-generating real artwork).
prompts:
	$(PY) tools/illustration_prompts.py

# Re-bake the cream paper-grain texture from the SVG filter (committed asset).
paper:
	$(PY) tools/bake_paper.py

# Builds both build/cookbook.html (print) and build/epub.html (semantic).
html: illustrations
	$(PY) tools/build_html.py

pdf: html
	$(NODE) tools/make_pdf.mjs

epub: html
	bash tools/make_epub.sh

validate:
	$(PY) tools/validate.py

migrate:
	$(PY) tools/migrate.py

clean:
	rm -rf $(BUILD)/cookbook.html $(BUILD)/epub.html $(BUILD)/cookbook.pdf \
	       $(BUILD)/cookbook.epub $(BUILD)/contact-sheet.png $(BUILD)/pdf_png
