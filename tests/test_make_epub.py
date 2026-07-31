"""Unit tests for make_epub's pandoc invocation."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from ladle import config, make_epub


def _book_with_theme(tmp_path, monkeypatch, mutate_theme=None) -> Path:
    """A copy of the sample book carrying its own copy of the bundled theme."""
    monkeypatch.setenv("LADLE_BUILD", str(tmp_path / "build"))
    book_dir = Path(shutil.copytree(config.SAMPLE_BOOK.parent, tmp_path / "book"))
    theme_dir = Path(shutil.copytree(config.PACKAGE_ROOT / "themes" / "default", book_dir / "themes" / "mine"))
    if mutate_theme:
        mutate_theme(theme_dir)
    book_path = book_dir / "book.yaml"
    book = yaml.safe_load(book_path.read_text(encoding="utf-8"))
    book["theme"] = "themes/mine"
    book_path.write_text(yaml.safe_dump(book), encoding="utf-8")
    return book_path


def _pandoc_argv(tmp_path, monkeypatch, mutate_theme=None) -> list[str]:
    """The argv make_epub would hand pandoc, without running it."""
    book_path = _book_with_theme(tmp_path, monkeypatch, mutate_theme)
    (tmp_path / "build").mkdir(parents=True, exist_ok=True)
    (tmp_path / "build" / "epub.html").write_text("<h1>x</h1>", encoding="utf-8")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/pandoc" if name == "pandoc" else None)
    captured: list[list[str]] = []

    def fake_run(cmd, *a, **kw):
        captured.append(list(cmd))
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    make_epub.render(str(book_path))
    return captured[-1]


def test_epub_css_comes_from_the_manifest(tmp_path, monkeypatch):
    argv = _pandoc_argv(tmp_path, monkeypatch)
    assert [a for a in argv if a.startswith("--css=")] == [
        f"--css={tmp_path / 'book' / 'themes' / 'mine' / 'css' / 'epub.css'}"
    ]


def test_a_theme_can_rename_its_epub_stylesheet(tmp_path, monkeypatch):
    # The core no longer knows the filename, so a theme is free to rename it.
    def rename(theme_dir):
        (theme_dir / "css" / "epub.css").rename(theme_dir / "css" / "reflow.css")
        manifest = theme_dir / "theme.yaml"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(text.replace("epub: [css/epub.css]", "epub: [css/reflow.css]"), encoding="utf-8")

    argv = _pandoc_argv(tmp_path, monkeypatch, rename)
    css = [a for a in argv if a.startswith("--css=")]
    assert len(css) == 1 and css[0].endswith("reflow.css")


def test_a_theme_can_declare_several_epub_stylesheets(tmp_path, monkeypatch):
    # pandoc takes --css more than once, in cascade order.
    def add(theme_dir):
        (theme_dir / "css" / "extra.css").write_text("p{}", encoding="utf-8")
        manifest = theme_dir / "theme.yaml"
        text = manifest.read_text(encoding="utf-8")
        manifest.write_text(
            text.replace("epub: [css/epub.css]", "epub: [css/epub.css, css/extra.css]"), encoding="utf-8"
        )

    css = [a for a in _pandoc_argv(tmp_path, monkeypatch, add) if a.startswith("--css=")]
    assert [Path(a.removeprefix("--css=")).name for a in css] == ["epub.css", "extra.css"]


def test_embedded_fonts_come_from_the_manifest(tmp_path, monkeypatch):
    argv = _pandoc_argv(tmp_path, monkeypatch)
    embedded = [Path(a.removeprefix("--epub-embed-font=")).name for a in argv if a.startswith("--epub-embed-font=")]
    assert sorted(embedded) == ["Bitter-Italic.ttf", "Bitter.ttf", "PlayfairDisplay-Italic.ttf", "PlayfairDisplay.ttf"]
