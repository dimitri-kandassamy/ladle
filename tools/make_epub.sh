#!/usr/bin/env bash
# Build build/cookbook.epub from build/epub.html with pandoc, then validate.
# The EPUB cover reuses the designed PDF cover (first page rasterised).
set -euo pipefail
cd "$(dirname "$0")/.."

BOOK_PATH="${BOOK_CONFIG:-book.yaml}"
while [ $# -gt 0 ]; do
  case "$1" in
    --book) BOOK_PATH="$2"; shift 2 ;;
    --book=*) BOOK_PATH="${1#--book=}"; shift ;;
    *) echo "Unknown argument: $1" >&2; exit 1 ;;
  esac
done

[ -f build/epub.html ] || { echo "Missing build/epub.html — run python3 tools/build_html.py first." >&2; exit 1; }

# Cover: rasterise the designed PDF cover when available.
COVER_ARGS=()
if [ -f build/cookbook.pdf ]; then
  pdftoppm -r 150 -png -f 1 -l 1 -singlefile build/cookbook.pdf build/cover >/dev/null 2>&1 || true
fi
[ -f build/cover.png ] && COVER_ARGS=(--epub-cover-image=build/cover.png)

yaml_get() { python3 -c "import sys,yaml;print(yaml.safe_load(open(sys.argv[1]))[sys.argv[2]])" "$BOOK_PATH" "$1"; }
TITLE=$(yaml_get title)
RIGHTS=$(yaml_get rights)
LANG=$(yaml_get language)

FONT_ARGS=()
for f in PlayfairDisplay PlayfairDisplay-Italic Bitter Bitter-Italic; do
  FONT_ARGS+=(--epub-embed-font="assets/fonts/$f.ttf")
done

pandoc build/epub.html -o build/cookbook.epub \
  --from html --to epub3 \
  --metadata title="$TITLE" \
  --metadata author="The Community Cookbook contributors" \
  --metadata lang="$LANG" \
  --metadata rights="$RIGHTS" \
  --css assets/css/epub.css \
  --split-level=1 \
  --resource-path=".:build" \
  --toc --toc-depth=1 \
  "${COVER_ARGS[@]}" "${FONT_ARGS[@]}"

echo "Wrote build/cookbook.epub"
# EPUB validation (epubcheck) lives in tools/validate.py — `make validate`.
