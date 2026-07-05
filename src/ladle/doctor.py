#!/usr/bin/env python3
"""Preflight: check the tools this pipeline needs are installed, before a build
fails opaquely three steps in.

Checks pandoc, poppler (pdfinfo/pdftoppm), WeasyPrint (and its system libs),
core Python packages, and Java/epubcheck (optional). Prints actionable,
per-OS install instructions for anything missing.

Exit code is non-zero only if a *required* dependency is missing; Java/epubcheck
are warnings (validate.py already falls back to a structural check without them).

Run: ladle doctor
"""
from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
import sys

from . import config
from .validate import find_java  # reuses the same JDK-probing logic

required_failures: list[str] = []


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m" if sys.stdout.isatty() else f"\n{title}")


def ok(msg: str) -> None:
    print(f"  ok   {msg}")


def warn(msg: str) -> None:
    print(f"  warn {msg}")


def bad(msg: str, *, required: bool = True) -> None:
    print(f"  FAIL {msg}")
    if required:
        required_failures.append(msg)


def check_python() -> None:
    section("Python")
    if sys.version_info >= (3, 11):
        ok(f"Python {platform.python_version()}")
    else:
        bad(f"Python {platform.python_version()} — need >= 3.11")


def check_pandoc() -> None:
    section("pandoc")
    exe = shutil.which("pandoc")
    if not exe:
        bad("pandoc not found on PATH")
        return
    res = subprocess.run(["pandoc", "--version"], capture_output=True, text=True)
    ok(res.stdout.splitlines()[0] if res.stdout else "pandoc found")


def check_poppler() -> None:
    section("poppler (pdfinfo / pdftoppm)")
    missing = [tool for tool in ("pdfinfo", "pdftoppm") if not shutil.which(tool)]
    if missing:
        bad(f"missing: {', '.join(missing)}")
    else:
        ok("pdfinfo and pdftoppm found")


def check_weasyprint() -> None:
    section("WeasyPrint")
    try:
        importlib.import_module("weasyprint")
        ok("weasyprint importable")
    except ImportError:
        bad("weasyprint not installed — pip install -r requirements.txt")
    except OSError as e:
        bad(f"weasyprint installed but its system libs (Pango/cairo) failed to load: {e}")


def check_python_packages() -> None:
    section("Python packages")
    # module import name -> pip package name (only where they differ)
    packages = {
        "yaml": "PyYAML",
        "jinja2": "Jinja2",
        "jsonschema": "jsonschema",
        "cairosvg": "cairosvg",
        "PIL": "Pillow",
        "numpy": "numpy",
    }
    missing = []
    for module, pip_name in packages.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)
    if missing:
        bad(f"missing: {', '.join(missing)} — pip install -r requirements.txt")
    else:
        ok("all required packages importable")


def check_java_epubcheck() -> None:
    section("Java + epubcheck (optional — validate.py falls back without them)")
    java = find_java()
    if java:
        ok(f"working Java found: {java}")
    else:
        warn("no working Java found — epubcheck will be skipped in favor of a structural fallback")
    jar = config.epubcheck_jar()
    if jar.exists():
        ok(f"{config.rel(jar)} present")
    else:
        warn(f"{config.rel(jar)} not present — see README for how CI installs it")


def install_hints() -> None:
    section("Install hints for anything missing above")
    system = platform.system()
    if system == "Darwin":
        print("  macOS (Homebrew):")
        print("    brew install pango poppler pandoc")
        print("    brew install openjdk   # optional, for epubcheck")
        print("    pip install -r requirements.txt")
    elif system == "Linux":
        print("  Linux (Debian/Ubuntu, matching .github/workflows/build.yml):")
        print("    sudo apt-get update")
        print("    sudo apt-get install -y poppler-utils \\")
        print("      libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \\")
        print("      libgdk-pixbuf-2.0-0 libffi-dev libcairo2")
        print("    # pandoc: distro packages lag and can emit broken EPUB cross-references;")
        print("    # install the pinned release instead (see build.yml's PANDOC_VERSION)")
        print("    curl -sL https://github.com/jgm/pandoc/releases/download/3.10/pandoc-3.10-1-amd64.deb -o pandoc.deb")
        print("    sudo apt-get install -y ./pandoc.deb")
        print("    pip install -r requirements.txt")
    else:
        print(f"  {system}: see README.md's Requirements section for what to install.")


def main(argv: list[str] | None = None) -> int:
    check_python()
    check_pandoc()
    check_poppler()
    check_weasyprint()
    check_python_packages()
    check_java_epubcheck()

    if required_failures:
        install_hints()

    section("Summary")
    if required_failures:
        print(f"  \033[31m{len(required_failures)} required check(s) failed.\033[0m")
        return 1
    print("  All required checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
