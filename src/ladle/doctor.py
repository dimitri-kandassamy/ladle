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

from . import config, ui
from .validate import find_java  # reuses the same JDK-probing logic

required_failures: list[str] = []


def section(title: str) -> None:
    ui.step("")
    ui.step(ui.style(title, "bold"))


def ok(msg: str) -> None:
    ui.step(f"  ok   {msg}")


def warn(msg: str) -> None:
    ui.step(f"  warn {msg}")


def bad(msg: str, *, required: bool = True) -> None:
    ui.step(f"  {ui.style('FAIL', 'red')} {msg}")
    if required:
        required_failures.append(msg)


def check_python() -> None:
    section("Python")
    if sys.version_info >= (3, 11):  # noqa: UP036 — runtime diagnostic; reports the user's actual Python
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
        ui.step("  macOS (Homebrew):")
        ui.step("    brew install pango poppler pandoc")
        ui.step("    brew install openjdk   # optional, for epubcheck")
        ui.step("    pip install -r requirements.txt")
    elif system == "Linux":
        ui.step("  Linux (Debian/Ubuntu, matching .github/workflows/build.yml):")
        ui.step("    sudo apt-get update")
        ui.step("    sudo apt-get install -y poppler-utils \\")
        ui.step("      libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \\")
        ui.step("      libgdk-pixbuf-2.0-0 libffi-dev libcairo2")
        ui.step("    # pandoc: distro packages lag and can emit broken EPUB cross-references;")
        ui.step("    # install the pinned release instead (see build.yml's PANDOC_VERSION)")
        ui.step("    curl -sLO https://github.com/jgm/pandoc/releases/download/3.10/pandoc-3.10-1-amd64.deb")
        ui.step("    sudo apt-get install -y ./pandoc-3.10-1-amd64.deb")
        ui.step("    pip install -r requirements.txt")
    else:
        ui.step(f"  {system}: see README.md's Requirements section for what to install.")


def main(argv: list[str] | None = None) -> int:
    ui.command_parser(__doc__, "ladle doctor").parse_args(argv)
    required_failures.clear()  # re-entrant across calls in one process
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
        ui.step(ui.style(f"  {len(required_failures)} required check(s) failed.", "red"))
        return 1
    ui.step("  All required checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
