#!/usr/bin/env bash
# Build build/cookbook.epub from build/epub.html with pandoc, then validate.
# The EPUB cover reuses the designed PDF cover (first page rasterised).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -f build/epub.html ] || { echo "Missing build/epub.html — run python3 tools/build_html.py first." >&2; exit 1; }

# Cover: rasterise the designed PDF cover when available.
COVER_ARGS=()
if [ -f build/cookbook.pdf ]; then
  pdftoppm -r 150 -png -f 1 -l 1 -singlefile build/cookbook.pdf build/cover >/dev/null 2>&1 || true
fi
[ -f build/cover.png ] && COVER_ARGS=(--epub-cover-image=build/cover.png)

TITLE=$(python3 -c "import yaml;print(yaml.safe_load(open('book.yaml'))['title'])")
RIGHTS=$(python3 -c "import yaml;print(yaml.safe_load(open('book.yaml'))['rights'])")

FONT_ARGS=()
for f in PlayfairDisplay PlayfairDisplay-Italic Bitter Bitter-Italic; do
  FONT_ARGS+=(--epub-embed-font="assets/fonts/$f.ttf")
done

pandoc build/epub.html -o build/cookbook.epub \
  --from html --to epub3 \
  --metadata title="$TITLE" \
  --metadata author="The Community Cookbook contributors" \
  --metadata lang=en \
  --metadata rights="$RIGHTS" \
  --css assets/css/epub.css \
  --split-level=1 \
  --resource-path=".:build" \
  --toc --toc-depth=1 \
  "${COVER_ARGS[@]}" "${FONT_ARGS[@]}"

echo "Wrote build/cookbook.epub"
# EPUB validation (epubcheck) lives in tools/validate.py — `make validate`.
