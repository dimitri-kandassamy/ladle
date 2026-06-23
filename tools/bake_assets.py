#!/usr/bin/env python3
"""Bake the raster brand assets the PDF build consumes — Python only, no browser.

The PDF renderer (WeasyPrint) reads ordinary raster backgrounds, so the page
textures and decorative line-art patterns are pre-rendered here and committed:

  * paper-cream.jpg  — soft cream paper grain (full-page cover background)
  * paper-navy.png   — navy paper grain tile (repeated on navy pages)
  * cover.png        — cover line-art food pattern   (rasterised from cover.svg)
  * endpaper.png     — endpaper line-art food pattern (rasterised from endpaper.svg)

Baking once and committing keeps the build a single, fast, dependency-light step
(no live SVG filters or blend modes, which renderers handle inconsistently).

Usage: python3 tools/bake_assets.py
"""
from __future__ import annotations

from pathlib import Path

import cairosvg
import numpy as np
from PIL import Image, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
PATTERNS = ROOT / "assets" / "illustrations" / "patterns"

CREAM = (250, 239, 219)  # #faefdb
NAVY = (22, 32, 58)      # #16203a


def grain(size: tuple[int, int], *, alpha: float, blur: float, seed: int) -> Image.Image:
    """A faint, soft luminance-noise layer to multiply over a flat colour."""
    rng = np.random.default_rng(seed)
    noise = rng.normal(0.5, 0.5, (size[1], size[0])).clip(0, 1)
    img = Image.fromarray((noise * 255).astype("uint8"), "L").filter(
        ImageFilter.GaussianBlur(blur)
    )
    # Compress the noise toward white so the grain stays subtle (1 - alpha .. 1).
    lo = int(255 * (1 - alpha))
    return img.point(lambda v: lo + v * (255 - lo) // 255).convert("RGB")


def bake_paper(color: tuple[int, int, int], size, *, alpha, blur, seed) -> Image.Image:
    base = Image.new("RGB", size, color)
    return ImageChops.multiply(base, grain(size, alpha=alpha, blur=blur, seed=seed))


def main() -> int:
    PATTERNS.mkdir(parents=True, exist_ok=True)

    cream = bake_paper(CREAM, (1350, 1900), alpha=0.06, blur=0.6, seed=7)
    cream.save(PATTERNS / "paper-cream.jpg", quality=86)

    navy = bake_paper(NAVY, (256, 256), alpha=0.10, blur=0.5, seed=11)
    navy.save(PATTERNS / "paper-navy.png")

    for name in ("cover", "endpaper"):
        cairosvg.svg2png(
            url=str(PATTERNS / f"{name}.svg"),
            write_to=str(PATTERNS / f"{name}.png"),
            output_width=1360,
            output_height=1900,
        )

    print("Baked paper-cream.jpg, paper-navy.png, cover.png, endpaper.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
