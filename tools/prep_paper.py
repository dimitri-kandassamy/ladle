#!/usr/bin/env python3
"""Turn a light paper-noise tile into the page grain used by print.css.

Shared/free paper-noise textures are often near-white (very low contrast). Used
raw they are invisible over the cream page, so we stretch the tonal range so the
grain reads, then commit the result as the seamless tile that print.css multiplies
over each page colour.

Usage:
  python3 tools/prep_paper.py SOURCE.png [--strength 3.5] [--out PATH]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "illustrations" / "patterns" / "paper-tile.png"


def main() -> int:
    ap = argparse.ArgumentParser(description="Contrast-boost a paper-noise tile.")
    ap.add_argument("source", help="path to a (seamless) paper-noise image")
    ap.add_argument("--strength", type=float, default=3.5,
                    help="multiplier on each pixel's darkness (higher = more visible grain)")
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    grain = Image.open(args.source).convert("L").point(
        lambda v: max(0, 255 - int((255 - v) * args.strength))
    )
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    grain.convert("RGB").save(args.out)
    lo, hi = grain.getextrema()
    print(f"wrote {args.out} (tonal range {lo}-{hi}, strength {args.strength})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
