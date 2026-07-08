#!/usr/bin/env python3
"""Build <build>/cookbook.epub from <build>/epub.html with pandoc.

Reads title/rights/language from the book's book.yaml, embeds the active theme's
fonts and EPUB CSS, and reuses the designed PDF cover (its first page rasterised)
as the EPUB cover when a PDF has already been built. EPUB validation lives in
`ladle validate`.
"""

from __future__ import annotations

import os
import shutil
import subprocess

from . import config, ui


def main(argv: list[str] | None = None) -> int:
    ap = ui.command_parser("ladle epub", __doc__, "ladle epub --book books/pt/book.yaml")
    config.add_book_arg(ap)
    args = ap.parse_args(argv)
    book_cfg = config.load_book_config(args.book)
    book = book_cfg.data

    if not shutil.which("pandoc"):
        return ui.die("pandoc not found on PATH", ui.ERROR, hint="see `ladle doctor`")

    build = config.build_dir()
    epub_html = build / "epub.html"
    if not epub_html.exists():
        return ui.die(f"missing {config.rel(epub_html)}", ui.ERROR, hint="run `ladle html` first")

    theme = book_cfg.theme_dir
    css = theme / "css" / "epub.css"
    font_files = list(dict.fromkeys(f["file"] for f in config.load_theme(theme)["font_faces"]))

    title = str(book.get("title", "Cookbook"))
    rights = str(book.get("rights", ""))
    lang = str(book.get("language", "en"))
    author = str(book.get("author", f"{title} contributors"))

    # Cover: rasterise the first PDF page when a PDF has been built.
    cover_args: list[str] = []
    pdf = build / "cookbook.pdf"
    if pdf.exists() and shutil.which("pdftoppm"):
        subprocess.run(
            ["pdftoppm", "-r", "150", "-png", "-f", "1", "-l", "1", "-singlefile", str(pdf), str(build / "cover")],
            capture_output=True,
        )
    cover_png = build / "cover.png"
    if cover_png.exists():
        cover_args = [f"--epub-cover-image={cover_png}"]

    font_args = [f"--epub-embed-font={theme / 'fonts' / f}" for f in font_files]

    # pandoc resolves relative resource paths (per-recipe illustrations in the
    # epub HTML) against these dirs; "." is the cwd, where those paths were
    # expressed by build_html, and <build> holds the cover.
    resource_path = os.pathsep.join([".", str(build)])
    out = build / "cookbook.epub"

    # Only pass non-empty metadata: an empty `rights` becomes an empty
    # <dc:rights> element, which epubcheck rejects (RSC-005). So a minimal
    # book.yaml without a `rights:` field still produces a valid EPUB.
    meta = [("title", title), ("author", author), ("lang", lang)]
    if rights:
        meta.append(("rights", rights))
    meta_args = [arg for key, value in meta for arg in ("--metadata", f"{key}={value}")]

    cmd = [
        "pandoc",
        str(epub_html),
        "-o",
        str(out),
        "--from",
        "html",
        "--to",
        "epub3",
        *meta_args,
        "--css",
        str(css),
        "--split-level=1",
        "--resource-path",
        resource_path,
        "--toc",
        "--toc-depth=1",
        *cover_args,
        *font_args,
    ]
    res = subprocess.run(cmd)
    if res.returncode != 0:
        return res.returncode
    ui.success(f"Wrote {config.rel(out)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
