LADLE := PYTHONPATH=src python3 -m ladle
BUILD := build

BOOK      ?= examples/the-ladle-kitchen/book.yaml
BOOK_FLAG := $(if $(BOOK),--book $(BOOK),)

.PHONY: all pdf epub html validate test lint format check doctor new-book clean

all: pdf epub

# Unit tests + lint — the fast CI gate, no book toolchain required.
# pytest resolves `ladle` from src/ via pyproject's pythonpath setting.
test:
	python3 -m pytest

lint:
	python3 -m ruff check src tests
	python3 -m ruff format --check src tests

# Auto-format the tree in place (ruff format, the canonical style).
format:
	python3 -m ruff format src tests

check: lint test

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
