#!/usr/bin/env python3
"""Bake an SVG feTurbulence paper-grain filter into a static full-page texture.

A procedural SVG filter can't be embedded once in a paged PDF — Chrome rasterises
it per page, which exploded the file to ~100 MB. So we render the filter to a
single image here and use that as a normal page background (embedded once, ~0.2 MB).

This reproduces the soft cream paper grain: fractalNoise multiplied faintly over the
cream base. Requires Google Chrome / Chromium (same browser the PDF build uses).

Usage:
  python3 tools/bake_paper.py [--base "#faefdb"] [--alpha 0.07] [--freq 0.04]
                              [--octaves 3] [--size 1350x1900] [--quality 86]
"""
from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "illustrations" / "patterns" / "paper-cream.jpg"

HTML = """<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0}}
body{{width:{w}px;height:{h}px;background:{base};position:relative}}
body::before{{content:"";position:absolute;inset:0;filter:url(#paper-grain);
  mix-blend-mode:multiply;pointer-events:none}}
</style></head><body>
<svg style="position:absolute;width:0;height:0">
  <filter id="paper-grain">
    <feTurbulence type="fractalNoise" baseFrequency="{freq}" numOctaves="{octaves}" stitchTiles="stitch"/>
    <feColorMatrix type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 {alpha} 0"/>
  </filter>
</svg></body></html>"""


def find_chrome() -> str | None:
    candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium", "/usr/bin/chromium-browser",
    ]
    return next((c for c in candidates if Path(c).exists()), None)


def main() -> int:
    ap = argparse.ArgumentParser(description="Bake the cream paper-grain filter to an image.")
    ap.add_argument("--base", default="#faefdb", help="cream base colour")
    ap.add_argument("--alpha", type=float, default=0.07, help="grain opacity (lower = subtler)")
    ap.add_argument("--freq", type=float, default=0.04, help="feTurbulence baseFrequency")
    ap.add_argument("--octaves", type=int, default=3)
    ap.add_argument("--size", default="1350x1900", help="WxH pixels (≈ page aspect)")
    ap.add_argument("--quality", type=int, default=86)
    ap.add_argument("--out", default=str(OUT))
    args = ap.parse_args()

    chrome = find_chrome()
    if not chrome:
        print("Google Chrome / Chromium not found.")
        return 1
    w, h = (int(x) for x in args.size.lower().split("x"))

    with tempfile.TemporaryDirectory() as td:
        html = Path(td) / "paper.html"
        png = Path(td) / "paper.png"
        html.write_text(HTML.format(w=w, h=h, base=args.base, freq=args.freq,
                                    octaves=args.octaves, alpha=args.alpha), encoding="utf-8")
        subprocess.run(
            [chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
             "--force-device-scale-factor=1", f"--window-size={w},{h}",
             "--virtual-time-budget=3000", f"--screenshot={png}", html.as_uri()],
            check=True, capture_output=True,
        )
        from PIL import Image

        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        Image.open(png).convert("RGB").save(out, quality=args.quality)
        print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size // 1024} KB, "
              f"{w}x{h}, alpha {args.alpha}, freq {args.freq})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
