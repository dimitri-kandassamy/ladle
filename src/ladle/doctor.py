#!/usr/bin/env python3
"""Preflight: check the tools this pipeline needs are installed, before a build
fails opaquely three steps in.

Checks pandoc, poppler (pdfinfo/pdftoppm), WeasyPrint (and its system libs),
core Python packages, and Java/epubcheck (optional). Prints actionable, per-OS
install instructions for anything missing.

With ``--install`` it offers to install what's missing for you: it prints the
exact package-manager commands (Homebrew on macOS, apt on Debian/Ubuntu, plus
``pip`` for Python packages) and asks before running them — or ``--yes`` to skip
the prompt. Nothing runs without your confirmation.

Exit code is non-zero only if a *required* dependency is missing; Java/epubcheck
are warnings (validate.py already falls back to a structural check without them).

Run: ladle doctor [--install [--yes]]
"""

from __future__ import annotations

import importlib
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from . import config, ui
from .validate import find_java  # reuses the same JDK-probing logic


@dataclass
class Dep:
    """A missing dependency and how to install it, per package manager.

    ``brew``/``apt`` name system packages; ``pip`` names Python packages. A
    channel left ``None`` means "can't be auto-installed this way" (e.g. pandoc
    on apt, whose distro build lags and can emit broken EPUB cross-references —
    install the pinned release by hand instead).
    """

    label: str
    brew: list[str] | None = None
    apt: list[str] | None = None
    pip: list[str] | None = None
    required: bool = True


required_failures: list[str] = []
missing_deps: list[Dep] = []


def section(title: str) -> None:
    ui.step("")
    ui.step(ui.style(title, "bold"))


def ok(msg: str) -> None:
    ui.step(f"  ok   {msg}")


def warn(msg: str) -> None:
    ui.step(f"  warn {msg}")


def bad(msg: str, *, required: bool = True, dep: Dep | None = None) -> None:
    ui.step(f"  {ui.style('FAIL', 'red')} {msg}")
    if required:
        required_failures.append(msg)
    if dep is not None:
        missing_deps.append(dep)


def check_python() -> None:
    section("Python")
    if sys.version_info >= (3, 11):  # noqa: UP036 — runtime diagnostic; reports the user's actual Python
        ok(f"Python {platform.python_version()}")
    else:
        # Not auto-installable — swapping the running interpreter is out of scope.
        bad(f"Python {platform.python_version()} — need >= 3.11")


def check_pandoc() -> None:
    section("pandoc")
    exe = shutil.which("pandoc")
    if not exe:
        # apt=None: distro pandoc lags and can emit broken EPUB refs (see install_hints).
        bad("pandoc not found on PATH", dep=Dep("pandoc", brew=["pandoc"]))
        return
    res = subprocess.run(["pandoc", "--version"], capture_output=True, text=True)
    ok(res.stdout.splitlines()[0] if res.stdout else "pandoc found")


def check_poppler() -> None:
    section("poppler (pdfinfo / pdftoppm)")
    missing = [tool for tool in ("pdfinfo", "pdftoppm") if not shutil.which(tool)]
    if missing:
        bad(f"missing: {', '.join(missing)}", dep=Dep("poppler", brew=["poppler"], apt=["poppler-utils"]))
    else:
        ok("pdfinfo and pdftoppm found")


def check_weasyprint() -> None:
    section("WeasyPrint")
    try:
        importlib.import_module("weasyprint")
        ok("weasyprint importable")
    except ImportError:
        bad("weasyprint not installed", dep=Dep("weasyprint", pip=["weasyprint"]))
    except OSError as e:
        bad(
            f"weasyprint installed but its system libs (Pango/cairo) failed to load: {e}",
            dep=Dep(
                "Pango/cairo (WeasyPrint system libraries)",
                brew=["pango", "gdk-pixbuf", "libffi"],
                apt=[
                    "libpango-1.0-0",
                    "libpangocairo-1.0-0",
                    "libpangoft2-1.0-0",
                    "libgdk-pixbuf-2.0-0",
                    "libffi-dev",
                    "libcairo2",
                ],
            ),
        )


def check_python_packages() -> None:
    section("Python packages")
    # module import name -> pip package name (only where they differ)
    packages = {
        "yaml": "PyYAML",
        "jinja2": "Jinja2",
        "jsonschema": "jsonschema",
        "PIL": "Pillow",
    }
    missing = []
    for module, pip_name in packages.items():
        try:
            importlib.import_module(module)
        except ImportError:
            missing.append(pip_name)
    if missing:
        bad(f"missing: {', '.join(missing)}", dep=Dep("Python packages", pip=missing))
    else:
        ok("all required packages importable")


def check_java_epubcheck() -> None:
    section("Java + epubcheck (optional — validate.py falls back without them)")
    java = find_java()
    if java:
        ok(f"working Java found: {java}")
    else:
        warn("no working Java found — epubcheck will be skipped in favor of a structural fallback")
        # Optional: offered by --install alongside the rest, but never fails the run.
        missing_deps.append(
            Dep("openjdk (optional, for epubcheck)", brew=["openjdk"], apt=["default-jre"], required=False)
        )
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
    ui.step("")
    ui.step("  Or let ladle run these for you:  ladle doctor --install")


# ---- auto-install ---------------------------------------------------------
@dataclass
class InstallPlan:
    """Commands to run for the missing deps, plus what couldn't be automated."""

    commands: list[list[str]] = field(default_factory=list)
    manual: list[str] = field(default_factory=list)  # labels we can't auto-install here


def _system_manager() -> tuple[str, str] | None:
    """The (attribute, manager-name) for this platform, if its tool is present."""
    system = platform.system()
    if system == "Darwin" and shutil.which("brew"):
        return ("brew", "brew")
    if system == "Linux" and shutil.which("apt-get"):
        return ("apt", "apt-get")
    return None


def plan_install(deps: list[Dep]) -> InstallPlan:
    """Turn missing *deps* into concrete install commands for this platform."""
    plan = InstallPlan()
    mgr = _system_manager()
    system_pkgs: list[str] = []
    pip_pkgs: list[str] = []
    for dep in deps:
        names = getattr(dep, mgr[0]) if mgr else None
        if names:
            system_pkgs += names
        elif dep.pip:
            pip_pkgs += dep.pip
        else:
            # Has a system channel but not for this platform's manager (or no
            # manager at all) — surface it as a manual step.
            plan.manual.append(dep.label)

    if system_pkgs:
        if mgr[1] == "brew":
            plan.commands.append(["brew", "install", *system_pkgs])
        else:
            plan.commands.append(["sudo", "apt-get", "install", "-y", *system_pkgs])
    if pip_pkgs:
        plan.commands.append([sys.executable, "-m", "pip", "install", *pip_pkgs])
    return plan


def do_install(*, assume_yes: bool) -> None:
    """Preview and (on confirmation) run the install plan for the missing deps.

    Refreshes the check state afterwards so the caller's summary reflects reality.
    """
    plan = plan_install(missing_deps)

    section("Install")
    if plan.manual:
        warn(f"can't auto-install here: {', '.join(plan.manual)} — see the hints above")
    if not plan.commands:
        ui.step("  nothing to install automatically on this platform.")
        return

    ui.step("  will run:")
    for cmd in plan.commands:
        ui.step(f"    {' '.join(cmd)}")

    if not ui.confirm("Run the above now?", assume_yes=assume_yes):
        if not ui.interactive():
            ui.step("  skipped — re-run with --yes to install non-interactively.")
        else:
            ui.step("  skipped.")
        return

    for cmd in plan.commands:
        ui.step("")
        ui.step(ui.style(f"$ {' '.join(cmd)}", "dim"))
        result = subprocess.run(cmd)
        if result.returncode != 0:
            ui.warn(f"command failed (exit {result.returncode}): {' '.join(cmd)}")

    ui.step("")
    ui.step("Re-checking…")
    run_checks()


def run_checks() -> None:
    """Run every preflight check, (re)populating the module-level result lists."""
    required_failures.clear()
    missing_deps.clear()
    check_python()
    check_pandoc()
    check_poppler()
    check_weasyprint()
    check_python_packages()
    check_java_epubcheck()


def main(argv: list[str] | None = None) -> int:
    parser = ui.command_parser("ladle doctor", __doc__, "ladle doctor", "ladle doctor --install")
    parser.add_argument("--install", action="store_true", help="offer to install anything missing (brew/apt + pip)")
    parser.add_argument("--yes", "-y", action="store_true", help="with --install, don't prompt before running")
    args = parser.parse_args(argv)

    run_checks()

    if args.install and missing_deps:
        do_install(assume_yes=args.yes)

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
