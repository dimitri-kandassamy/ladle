#!/usr/bin/env python3
"""One-off importer: legacy heading-based recipes -> frontmatter recipes.

Reads the user's existing heading-only markdown recipes and rewrites each as a
`recipes/<slug>.md` with YAML front matter (metadata) + a clean body
(INGREDIENTS / DIRECTIONS / NOTES). Metadata that used to live in the body
(title, yields, credits) is lifted into front matter; ingredient group labels
like "Cake:" are normalised to `### Cake`.

Idempotent: rerunning overwrites the generated recipes. Safe to delete after the
import — new recipes are authored directly in the front-matter format.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
LEGACY = Path("/Users/aznaar/Code/dimitri-kandassamy/cookbook/Recipes")
OUT = ROOT / "recipes"

# Category mapping taken from the legacy README grouping.
CATEGORY = {
    "banana-cake": "Desserts",
    "carrot-cake": "Desserts",
    "chocolate-cake": "Desserts",
    "chocolate-fondant": "Desserts",
    "chocolate-mousse": "Desserts",
    "congolais": "Desserts",
    "keylime-cheesecake-nobake": "Desserts",
    "pineapple-cake": "Desserts",
    "arroz-cenoura": "Savory",
    "pate-lorrain": "Savory",
    "tea-heals-everything": "Beverages",
}


def split_sections(lines: list[str]) -> tuple[str, dict[str, list[str]]]:
    """Return (h1_title, {SECTION_NAME: body_lines}) keyed by `## NAME`."""
    title = ""
    sections: dict[str, list[str]] = {}
    current = None
    for line in lines:
        m1 = re.match(r"^#\s+(.*\S)\s*$", line)
        m2 = re.match(r"^##\s+(.*\S)\s*$", line)
        if m1 and not title:
            title = m1.group(1).strip()
            continue
        if m2:
            current = m2.group(1).strip().upper()
            sections[current] = []
            continue
        if current is not None:
            sections[current].append(line.rstrip("\n"))
    return title, sections


def extract_yields(ingredient_lines: list[str]) -> tuple[str, list[str]]:
    """Pull a `### YIELDS` subsection out of the INGREDIENTS body.

    Everything from `### YIELDS` up to the next heading (or end) is consumed; the
    first list item in that span becomes `servings`.

    Returns (servings, cleaned_ingredient_lines).
    """
    servings = ""
    cleaned: list[str] = []
    in_yields = False
    for line in ingredient_lines:
        if re.match(r"^###\s+YIELDS", line, re.IGNORECASE):
            in_yields = True
            continue
        if in_yields:
            if line.lstrip().startswith("#"):  # next heading ends the block
                in_yields = False
                cleaned.append(line)
                continue
            item = re.match(r"^\s*-\s+(.*\S)\s*$", line)
            if item and not servings:
                servings = item.group(1).strip()
            continue  # drop yields-block lines from the body
        cleaned.append(line)
    return servings, cleaned


def normalise_ingredients(lines: list[str]) -> list[str]:
    """Convert bare 'Group:' labels into `### Group` headings; trim blanks."""
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith(("-", "#", "*")) and stripped.endswith(":"):
            out.append(f"### {stripped[:-1].strip()}")
        else:
            out.append(line)
    return _trim(out)


def _trim(lines: list[str]) -> list[str]:
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def convert(path: Path) -> tuple[str, str]:
    slug = path.stem
    raw = path.read_text(encoding="utf-8")
    title, sections = split_sections(raw.splitlines())

    # Title may carry a trailing "by <Author>".
    credits = ""
    by = re.search(r"\bby\s+(.+)$", title, re.IGNORECASE)
    if by:
        credits = by.group(1).strip()
        title = title[: by.start()].strip()

    servings, ing = extract_yields(sections.get("INGREDIENTS", []))
    ing = normalise_ingredients(ing)
    directions = _trim(sections.get("DIRECTIONS", []))
    notes = _trim(sections.get("NOTES", []))
    if sections.get("CREDITS"):
        credits = " ".join(l.strip() for l in sections["CREDITS"] if l.strip()) or credits

    fm = {
        "title": title,
        "slug": slug,
        "category": CATEGORY.get(slug, "Savory"),
        "servings": servings or "—",
        "credits": credits or "Unknown",
        "story": "",
        "illustration": f"assets/illustrations/recipes/{slug}.svg",
        "draft": False,
    }
    front = yaml.safe_dump(fm, sort_keys=False, allow_unicode=True).strip()

    body = ["## INGREDIENTS", "", *ing, "", "## DIRECTIONS", "", *directions]
    if notes:
        body += ["", "## NOTES", "", *notes]
    body_text = "\n".join(body).strip() + "\n"

    return slug, f"---\n{front}\n---\n\n{body_text}"


def main() -> int:
    if not LEGACY.is_dir():
        print(f"legacy recipes not found: {LEGACY}", file=sys.stderr)
        return 1
    OUT.mkdir(parents=True, exist_ok=True)
    count = 0
    for path in sorted(LEGACY.glob("*.md")):
        slug, text = convert(path)
        (OUT / f"{slug}.md").write_text(text, encoding="utf-8")
        print(f"wrote recipes/{slug}.md")
        count += 1
    print(f"\nMigrated {count} recipe(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
