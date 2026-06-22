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

# Validate when epubcheck is available. Find a java even if it's keg-only.
find_java() {
  # Return the first candidate that is a *working* runtime. On macOS, the
  # /usr/bin/java stub is on PATH but errors unless a JDK is installed, so we
  # verify each candidate with `-version` rather than trusting `command -v`.
  local candidates=()
  [ -n "${JAVA_HOME:-}" ] && candidates+=("$JAVA_HOME/bin/java")
  candidates+=(/usr/local/opt/openjdk/bin/java /opt/homebrew/opt/openjdk/bin/java)
  command -v java >/dev/null 2>&1 && candidates+=("$(command -v java)")
  for j in "${candidates[@]}"; do
    [ -x "$j" ] && "$j" -version >/dev/null 2>&1 && { echo "$j"; return; }
  done
}
JAVA=$(find_java)
if [ -f tools/epubcheck/epubcheck.jar ] && [ -n "$JAVA" ]; then
  "$JAVA" -jar tools/epubcheck/epubcheck.jar build/cookbook.epub
elif command -v epubcheck >/dev/null 2>&1; then
  epubcheck build/cookbook.epub
else
  echo "(epubcheck/java not found — skipping validation; CI runs the full check)"
fi
