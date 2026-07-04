#!/usr/bin/env python3
"""Generate the cookbook's illustrations.

Two motifs, matching the art direction:
  * navy line-art *patterns* (cover / endpaper / back), white strokes on navy;
  * warm, hand-illustrated *food spots*, one per recipe, composed from a small
    library of vector motifs chosen by keywords in each recipe's title/tags.

This writes deterministic, on-brand **SVG placeholders** so every build is green
with zero dependencies or network. To create real artwork, generate each image by
hand in the locked style documented in DESIGN.md and save it as
assets/illustrations/recipes/<slug>.png — build_html.py prefers that raster over
the placeholder automatically.

Idempotent: existing files are skipped unless --force.

Usage:
  python3 tools/gen_illustrations.py [--force]
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from pathlib import Path

import yaml

from . import config

INK = "#3a2f25"
LEAF = "#7f9b53"


# ---- colour helpers --------------------------------------------------------
def _mix(hex_color: str, target: tuple[int, int, int], f: float) -> str:
    h = hex_color.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    tr, tg, tb = target
    return "#%02x%02x%02x" % (
        round(r + (tr - r) * f), round(g + (tg - g) * f), round(b + (tb - b) * f)
    )


def darken(c: str, f: float = 0.28) -> str:
    return _mix(c, (0, 0, 0), f)


def lighten(c: str, f: float = 0.35) -> str:
    return _mix(c, (255, 255, 255), f)


# ---- primitive element helpers ---------------------------------------------
def el(cx, cy, rx, ry, fill, opacity=1.0, stroke=None, sw=0.0) -> str:
    s = f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{rx:.1f}" ry="{ry:.1f}" fill="{fill}" opacity="{opacity:.2f}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{sw}"'
    return s + "/>"


def path(d, fill="none", opacity=1.0, stroke=None, sw=0.0) -> str:
    s = f'<path d="{d}" fill="{fill}" opacity="{opacity:.2f}"'
    if stroke:
        s += f' stroke="{stroke}" stroke-width="{sw}" stroke-linejoin="round" stroke-linecap="round"'
    return s + "/>"


def blob_path(cx, cy, r, rng, points=11, squash=1.0) -> str:
    pts = []
    for i in range(points):
        a = 2 * math.pi * i / points
        rr = r * rng.uniform(0.78, 1.12)
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a) * squash))
    d = f"M {pts[0][0]:.1f} {pts[0][1]:.1f} "
    for i in range(points):
        p0, p1 = pts[i], pts[(i + 1) % points]
        mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
        d += f"Q {p0[0]:.1f} {p0[1]:.1f} {mx:.1f} {my:.1f} "
    return d + "Z"


def leaf(cx, cy, rot, scale=1.0, color=LEAF) -> str:
    return (
        f'<g transform="translate({cx:.1f} {cy:.1f}) rotate({rot:.0f}) scale({scale:.2f})">'
        f'<path d="M0 0 Q 11 -16 0 -32 Q -11 -16 0 0 Z" fill="{color}"/>'
        f'<path d="M0 -3 L0 -27" stroke="{darken(color)}" stroke-width="1" fill="none"/></g>'
    )


def shadow(cx=230, cy=292, rx=150, ry=30) -> str:
    return el(cx, cy, rx, ry, "#000000", 0.06)


def plate(cx=230, cy=256, rx=158, ry=60) -> str:
    return (
        el(cx, cy, rx, ry, "#fffdf7", 1, "#d8cdb0", 2)
        + el(cx, cy - 3, rx * 0.72, ry * 0.72, "none", 1, "#ece2cb", 1)
    )


def mound(cx, cy, r, color, rng, points=11) -> str:
    d = blob_path(cx, cy, r, rng, points)
    parts = [
        path(blob_path(cx, cy, r * 1.07, rng, points), color, 0.22),  # watercolour bleed
        path(d, color, 0.96),
        path(blob_path(cx, cy + r * 0.22, r * 0.72, rng, points), darken(color, 0.22), 0.5),
        path(blob_path(cx - r * 0.28, cy - r * 0.3, r * 0.4, rng, 8), "#ffffff", 0.16),
        path(d, "none", 0.4, INK, 1.1),
    ]
    return "".join(parts)


# ---- dish scenes -----------------------------------------------------------
def s_plate_mound(rng, palette) -> str:
    parts = [shadow(), plate()]
    cx, cy = 230, 210
    for _ in range(3):
        col = rng.choice(palette)
        parts.append(mound(cx + rng.uniform(-44, 44), cy + rng.uniform(-6, 22),
                            rng.uniform(46, 66), col, rng))
    parts += [leaf(cx - 72, cy - 24, -24, 1.1), leaf(cx + 78, cy - 14, 26, 0.9)]
    return "".join(parts)


def cake_slice(cx, cy, sponge, frosting, rng, crust=None, top=True) -> str:
    tip = (cx - 72, cy + 4)
    br = (cx + 64, cy + 36)
    tr = (cx + 64, cy - 48)
    dx, dy = 16, -9
    front = f"M {tip[0]} {tip[1]} L {br[0]} {br[1]} L {tr[0]} {tr[1]} Z"
    side = f"M {br[0]} {br[1]} L {br[0]+dx} {br[1]+dy} L {tr[0]+dx} {tr[1]+dy} L {tr[0]} {tr[1]} Z"
    topface = f"M {tip[0]} {tip[1]} L {tip[0]+dx} {tip[1]+dy} L {tr[0]+dx} {tr[1]+dy} L {tr[0]} {tr[1]} Z"
    parts = [path(side, darken(sponge, 0.22)), path(front, sponge)]
    # cream layer line across the front
    parts.append(path(f"M {tip[0]+6} {tip[1]-16} L {br[0]} {br[1]-22}", "none", 0.9,
                       lighten(frosting, 0.2), 6))
    if crust:  # biscuit base band (cheesecake)
        parts.append(path(f"M {tip[0]} {tip[1]} L {br[0]} {br[1]} L {br[0]} {br[1]-9} "
                          f"L {tip[0]} {tip[1]-7} Z", crust))
    if top:
        parts.append(path(topface, frosting))
        parts.append(path(topface, "none", 0.4, INK, 1.0))
    parts.append(path(front, "none", 0.45, INK, 1.1))
    return "".join(parts)


def s_cake(rng, sponge, frosting, topper=None) -> str:
    parts = [shadow(), plate(), cake_slice(244, 214, sponge, frosting, rng)]
    if topper:  # garnish resting on the front-left of the plate
        parts.append(topper(168, 256, rng))
    return "".join(parts)


def s_cheesecake(rng) -> str:
    parts = [shadow(), plate(),
             cake_slice(244, 214, "#f3e6c4", "#f8efd6", rng, crust="#b07d4a", top=True)]
    # lime wheel + mint resting on the front-left of the plate
    lx, ly = 166, 256
    parts.append(el(lx, ly, 17, 17, "#8bbf4a", 1, darken("#8bbf4a"), 1.2))
    parts.append(el(lx, ly, 8, 8, "#d6ea9f", 0.9))
    parts.append(path(f"M {lx} {ly} L {lx-11} {ly-8} M {lx} {ly} L {lx+11} {ly-8} "
                      f"M {lx} {ly} L {lx} {ly-14} M {lx} {ly} L {lx-11} {ly+8} M {lx} {ly} L {lx+11} {ly+8}",
                      "none", 0.6, "#e9f3d2", 1))
    parts.append(leaf(lx + 26, ly - 10, 24, 0.8))
    return "".join(parts)


def s_teacup(rng) -> str:
    cx, cy = 230, 200
    parts = [shadow(cx, cy + 56, 96, 18), el(cx, cy + 34, 104, 22, "#fffdf7", 1, "#d8cdb0", 2)]
    cup = (f"M {cx-50} {cy-30} Q {cx-56} {cy+22} {cx-30} {cy+30} "
           f"L {cx+30} {cy+30} Q {cx+56} {cy+22} {cx+50} {cy-30} Z")
    parts.append(path(cup, "#fdfaf3", 1, INK, 1.6))
    parts.append(el(cx, cy - 30, 50, 13, "#c98a3a"))
    parts.append(el(cx, cy - 30, 50, 13, "none", 0.8, darken("#c98a3a"), 1))
    parts.append(el(cx - 16, cy - 32, 16, 4, "#e0ab64", 0.7))  # surface highlight
    parts.append(f'<path d="M {cx+50} {cy-18} q 30 2 28 26 q -2 20 -26 16" '
                 f'fill="none" stroke="{INK}" stroke-width="3.4"/>')
    for dx in (-16, 0, 16):
        parts.append(f'<path d="M {cx+dx} {cy-46} q 9 -11 0 -22 q -9 -11 0 -22" '
                     f'fill="none" stroke="#cdbfa0" stroke-width="2" opacity="0.7"/>')
    parts.append(el(cx + 64, cy - 6, 14, 14, "#e8c24b", 1, darken("#e8c24b"), 1))  # lemon
    parts.append(leaf(cx - 64, cy + 4, -28, 0.8))
    return "".join(parts)


def s_glass(rng) -> str:
    cx, cy = 230, 200
    top, bot, tw, bw = cy - 48, cy + 46, 42, 34
    body = (f"M {cx-tw} {top} L {cx-bw} {bot} Q {cx} {bot+10} {cx+bw} {bot} "
            f"L {cx+tw} {top} Q {cx} {top+9} {cx-tw} {top} Z")
    parts = [shadow(cx, cy + 58, 64, 14), path(body, "#ffffff", 0.16, "#cdd4d8", 2)]
    mtop = cy - 28
    mousse = (f"M {cx-tw+3} {mtop} L {cx-bw+2} {bot-2} Q {cx} {bot+6} {cx+bw-2} {bot-2} "
              f"L {cx+tw-3} {mtop} Q {cx} {mtop+8} {cx-tw+3} {mtop} Z")
    parts.append(path(mousse, "#6b4636", 0.96))
    parts.append(path(mousse, "none", 0.3, darken("#6b4636"), 1))
    parts.append(el(cx, mtop, tw - 4, 9, "#f5ead6"))            # cream
    parts.append(path(blob_path(cx, mtop - 7, 17, rng, 9), "#f7efdd", 0.97))
    for _ in range(7):
        parts.append(f'<circle cx="{cx+rng.uniform(-18,18):.0f}" '
                     f'cy="{mtop-9+rng.uniform(-3,3):.0f}" r="1.4" fill="#5b3a29"/>')
    parts.append(f'<path d="M {cx-tw+7} {top+8} L {cx-bw+7} {bot-10}" '
                 f'stroke="#ffffff" stroke-width="3" opacity="0.5" fill="none"/>')
    parts.append(leaf(cx + 6, mtop - 16, 12, 0.6))
    return "".join(parts)


def s_fondant(rng) -> str:
    cx = 230
    parts = [shadow(), plate()]
    base = 228
    dome = (f"M {cx-60} {base} Q {cx-66} {base-66} {cx} {base-72} "
            f"Q {cx+66} {base-66} {cx+60} {base} Q {cx} {base+16} {cx-60} {base} Z")
    parts.append(path(dome, "#5b3a29", 1, "#3f281b", 1.6))
    parts.append(path(dome, "none", 0.2, "#ffffff", 1))
    for _ in range(26):  # icing-sugar dust
        parts.append(f'<circle cx="{cx+rng.uniform(-46,46):.0f}" '
                     f'cy="{base-30+rng.uniform(-34,8):.0f}" r="1.1" fill="#fff7e8" opacity="0.7"/>')
    parts.append(path(blob_path(cx, base - 60, 15, rng, 9), "#8a4a22", 0.97))  # cracked top
    parts.append(f'<path d="M {cx-8} {base-58} q 7 28 -3 48" stroke="#7a3f1f" '
                 f'stroke-width="6" fill="none" stroke-linecap="round"/>')      # molten drip
    parts.append(el(cx + 46, base - 4, 8, 8, "#b0324a"))
    parts.append(leaf(cx + 46, base - 12, 12, 0.7))
    return "".join(parts)


def s_cookies(rng) -> str:
    cx = 230
    parts = [shadow(), plate()]
    base = 236
    for dx in (-54, 2, 56):
        x = cx + dx
        h = 46 + rng.uniform(-3, 7)
        cone = (f"M {x-26} {base} Q {x} {base+8} {x+26} {base} "
                f"L {x+6} {base-h} Q {x} {base-h-7} {x-6} {base-h} Z")
        parts.append(path(cone, "#f0e6d2", 1, INK, 1.1))
        for _ in range(16):
            parts.append(f'<circle cx="{x+rng.uniform(-20,20):.0f}" '
                         f'cy="{base-rng.uniform(2,h-6):.0f}" r="1.1" fill="#cbb085" opacity="0.85"/>')
        parts.append(path(f"M {x-7} {base-h+9} Q {x} {base-h-7} {x+7} {base-h+9} Z", "#b07d4a"))
    return "".join(parts)


def s_pastry(rng) -> str:
    cx = 230
    parts = [shadow(), plate()]
    x0, x1, top, bot = cx - 72, cx + 72, 206, 262
    dome = (f"M {x0} {bot} Q {x0} {top} {cx} {top-6} Q {x1} {top} {x1} {bot} "
            f"Q {cx} {bot+12} {x0} {bot} Z")
    parts.append(path(dome, "#d99a4b", 1, darken("#d99a4b"), 1.6))
    parts.append(path(f"M {x0+14} {top+10} Q {cx} {top} {x1-14} {top+10}", "none", 0.6,
                      "#f0c277", 3))
    for i in range(3):
        lx = cx - 32 + i * 32
        parts.append(f'<path d="M {lx} {top+6} q 7 18 0 40" stroke="{darken("#d99a4b")}" '
                     f'stroke-width="1.2" fill="none" opacity="0.7"/>')
    parts += [leaf(x1 - 8, bot - 14, 22, 0.9), leaf(x0 + 12, bot - 12, -24, 0.8)]
    return "".join(parts)


def s_bowl(rng) -> str:
    bx, by = 230, 214
    rx = 120
    parts = [shadow(bx, by + 78, 122, 22)]
    body = f"M {bx-rx} {by} Q {bx} {by+96} {bx+rx} {by} Z"
    parts.append(path(body, "#e2d4b8", 1, "#cbbf9f", 2))
    parts.append(el(bx, by, rx, 46, "#e9ddc6", 1, "#cbbf9f", 2))
    parts.append(path(blob_path(bx, by - 6, rx * 0.82, rng, 13, squash=0.5), "#fbf5e6", 1))
    for _ in range(46):  # rice grains
        gx, gy = bx + rng.uniform(-rx * 0.7, rx * 0.7), by - 6 + rng.uniform(-22, 16)
        parts.append(f'<ellipse cx="{gx:.0f}" cy="{gy:.0f}" rx="3" ry="1.4" fill="#efe6cf" '
                     f'stroke="#e0d3b4" stroke-width="0.5" '
                     f'transform="rotate({rng.uniform(0,180):.0f} {gx:.0f} {gy:.0f})"/>')
    for _ in range(9):  # carrot dice
        gx, gy = bx + rng.uniform(-rx * 0.6, rx * 0.6), by - 8 + rng.uniform(-16, 12)
        parts.append(f'<rect x="{gx:.0f}" y="{gy:.0f}" width="8" height="8" rx="1.5" '
                     f'fill="#d97b2e" transform="rotate({rng.uniform(0,90):.0f} {gx:.0f} {gy:.0f})"/>')
    for _ in range(6):  # peas
        gx, gy = bx + rng.uniform(-rx * 0.6, rx * 0.6), by - 8 + rng.uniform(-16, 12)
        parts.append(el(gx, gy, 3.6, 3.6, "#7f9b53"))
    parts.append(leaf(bx, by - 42, 0, 1.0))
    return "".join(parts)


# fruit toppers (cx,cy = centre of the garnish)
def t_pineapple(cx, cy, rng) -> str:
    parts = [el(cx, cy, 22, 13, "#e8c24b", 1, darken("#e8c24b"), 1.4),
             el(cx, cy, 7, 4, "#caa235", 1, darken("#e8c24b"), 1)]
    parts.append(el(cx + 22, cy - 6, 7, 7, "#b0324a"))  # cherry
    parts.append(f'<path d="M {cx+22} {cy-12} q 4 -6 9 -6" stroke="{darken(LEAF)}" '
                 f'stroke-width="1.5" fill="none"/>')
    return "".join(parts)


def t_banana(cx, cy, rng) -> str:
    return path(f"M {cx-22} {cy+6} Q {cx} {cy-20} {cx+24} {cy+2} "
                f"Q {cx+4} {cy+12} {cx-22} {cy+6} Z", "#e8c24b", 1, darken("#e8c24b"), 1.4)


def t_carrot(cx, cy, rng) -> str:
    parts = [path(f"M {cx-16} {cy-8} L {cx+18} {cy-2} L {cx-12} {cy+10} Z", "#d97b2e", 1,
                  darken("#d97b2e"), 1.2)]
    for d in (-6, 0, 6):
        parts.append(leaf(cx - 16 + d * 0.4, cy - 10, d, 0.5))
    return "".join(parts)


# ---- scene selection -------------------------------------------------------
CAKE_FLAVOURS = {
    "chocolate": ("#5b3a29", "#6e4631"),
    "carrot": ("#c98a4f", "#fbf3e3"),
    "banana": ("#e8c87a", "#f3e7c8"),
    "pineapple": ("#e8c86a", "#f6ecca"),
    "lemon": ("#ecd98a", "#f7eed2"),
}


def scene_svg(recipe: dict) -> str:
    slug, title, category = recipe["slug"], recipe["title"], recipe["category"]
    hay = f"{title} {slug} {' '.join(recipe.get('tags', []))}".lower()
    rng = random.Random(slug)

    def has(*ks):
        return any(k in hay for k in ks)

    if has("tea", "infusion", "latte", "coffee") or (category == "Beverages" and not has("smoothie")):
        inner = s_teacup(rng)
    elif has("mousse", "pudding", "panna"):
        inner = s_glass(rng)
    elif has("fondant", "lava", "molten"):
        inner = s_fondant(rng)
    elif has("cheesecake"):
        inner = s_cheesecake(rng)
    elif has("congolais", "cookie", "biscuit", "macaroon", "coconut", "meringue"):
        inner = s_cookies(rng)
    elif has("pate", "lorrain", "pie", "pastry", "tart", "quiche", "empanada", "roll"):
        inner = s_pastry(rng)
    elif has("rice", "arroz", "risotto", "pilaf", "bowl", "soup", "stew", "curry", "salad", "chili"):
        inner = s_bowl(rng)
    elif has("cake", "gateau", "sponge", "loaf"):
        flavour = next((CAKE_FLAVOURS[k] for k in CAKE_FLAVOURS if k in hay), ("#d9b46e", "#f3e7c8"))
        topper = None
        if has("pineapple"):
            topper = t_pineapple
        elif has("banana"):
            topper = t_banana
        elif has("carrot"):
            topper = t_carrot
        inner = s_cake(rng, flavour[0], flavour[1], topper)
    else:
        palette = {"Desserts": ["#d98c6a", "#c96a78", "#e0a3b0"],
                   "Beverages": ["#c98a3a", "#d9a441"]}.get(
            category, ["#c0533b", "#d98026", "#7f9b53"])
        inner = s_plate_mound(rng, palette)

    # Tight viewBox frames the art (which lives roughly x:55-390, y:105-325) so it
    # fills its box instead of floating small inside wide empty margins.
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="45 95 370 250">{inner}</svg>'


# ---- navy line-art patterns ------------------------------------------------
GLYPHS = [
    '<circle cx="0" cy="0" r="26"/><circle cx="0" cy="0" r="17"/>',
    '<path d="M-22 -10 Q 0 -28 22 -10 Q 0 18 -22 -10 Z"/><path d="M0 -22 L0 12"/>',
    '<path d="M-4 -26 L-4 26 M4 -26 L4 26 M-12 -26 L-12 -6 Q -12 4 -4 4"/>',
    '<rect x="-16" y="-22" width="32" height="44" rx="6"/><rect x="-10" y="-30" width="20" height="10"/>',
    '<ellipse cx="0" cy="0" rx="24" ry="14"/><path d="M-24 0 Q 0 22 24 0"/>',
    '<path d="M-18 22 Q -26 -10 0 -24 Q 26 -10 18 22 Z"/>',
]


# Page grain and the navy line-art pattern PNGs are baked by tools/bake_assets.py
# (paper-cream.jpg, paper-navy.png, cover.png, endpaper.png) and committed. They
# are not generated here.


def pattern_svg(seed: int, density: float) -> str:
    rng = random.Random(seed)
    W, H, cols, rows = 680, 950, 5, 7
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}">',
        '<g fill="none" stroke="#f4ead2" stroke-width="1.6" stroke-linejoin="round" '
        'stroke-linecap="round" opacity="0.55">',
    ]
    for r in range(rows):
        for c in range(cols):
            if rng.random() > density:
                continue
            x = (c + 0.5) * W / cols + rng.uniform(-30, 30)
            y = (r + 0.5) * H / rows + rng.uniform(-34, 34)
            parts.append(
                f'<g transform="translate({x:.0f} {y:.0f}) rotate({rng.uniform(-25,25):.0f}) '
                f'scale({rng.uniform(0.85,1.5):.2f})">{rng.choice(GLYPHS)}</g>'
            )
    parts.append("</g></svg>")
    return "\n".join(parts)


# ---- driver ----------------------------------------------------------------
def load_recipes(recipes_dir: Path) -> list[dict]:
    out = []
    for p in sorted(recipes_dir.glob("*.md")):
        raw = p.read_text(encoding="utf-8")
        fm = yaml.safe_load(raw.split("---", 2)[1]) if raw.startswith("---") else {}
        out.append({
            "slug": fm.get("slug", p.stem),
            "title": fm.get("title", p.stem),
            "category": fm.get("category", "Savory"),
            "tags": fm.get("tags", []) or [],
        })
    return out


def write(path_: Path, content: str, force: bool) -> None:
    if path_.exists() and not force:
        return
    path_.parent.mkdir(parents=True, exist_ok=True)
    path_.write_text(content, encoding="utf-8")
    print(f"wrote {config.rel(path_)}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate the built-in SVG placeholder illustrations. "
        "To create real artwork, see the locked style in DESIGN.md and drop the "
        "resulting PNG next to each placeholder — the build prefers it automatically."
    )
    ap.add_argument("--force", action="store_true", help="overwrite existing art")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    book_cfg = config.load_book_config(args.book)

    patterns = book_cfg.theme_dir / "illustrations" / "patterns"
    write(patterns / "cover.svg", pattern_svg(1, 0.95), args.force)
    write(patterns / "endpaper.svg", pattern_svg(2, 0.8), args.force)
    write(patterns / "back.svg", pattern_svg(3, 0.7), args.force)

    for r in load_recipes(book_cfg.recipes_dir):
        write(book_cfg.illustrations_dir / f"{r['slug']}.svg", scene_svg(r), args.force)

    return 0


if __name__ == "__main__":
    sys.exit(main())
