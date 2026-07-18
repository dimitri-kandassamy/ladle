#!/usr/bin/env python3
"""Work with themes. Today: `ladle theme lint` — the featured-gallery gate.

The safety model (PLAN.md): anyone may build and use their own theme *at their
own risk* (themes install by path, no gate), but a theme shown in the community
gallery must lint clean. `ladle theme lint <theme>` runs the three Phase 0
checks that make a theme a trustworthy, portable bundle:

  1. **manifest** — theme.yaml exists and validates against theme.schema.json;
  2. **sandbox** — the print/epub templates exist and load in the Jinja
     sandbox (untrusted theme templates are rendered as data, never code);
  3. **fonts** — every embedded font family names a file that exists and carries
     a documented, redistribution-friendly license.

Exit code is non-zero if any check fails. Run: ladle theme lint <theme>
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from jinja2 import TemplateError

from . import build_html, config, ui

# Templates a theme must provide (the two renderers in build_html.render).
REQUIRED_TEMPLATES = ("print.html.j2", "epub.html.j2")

# Font licenses that permit embedding + redistribution in a distributed book.
# Matched against a normalized (lowercased, alphanumeric-only) license string by
# prefix, so "OFL-1.1", "SIL Open Font License 1.1", and "Apache-2.0" all pass.
_PERMISSIBLE_LICENSE_PREFIXES = (
    "ofl",
    "silopenfont",
    "apache",
    "mit",
    "ufl",
    "ubuntufont",
    "cc0",
    "publicdomain",
)


def _license_permissible(license_str: str) -> bool:
    return re.sub(r"[^a-z0-9]", "", license_str.lower()).startswith(_PERMISSIBLE_LICENSE_PREFIXES)


# A lint result is one record: {level: ok|fail|note, message}. Pure check
# functions return these so the report (and the tests) format from the data.
def _ok(message: str) -> dict:
    return {"level": "ok", "message": message}


def _fail(message: str) -> dict:
    return {"level": "fail", "message": message}


def _note(message: str) -> dict:
    return {"level": "note", "message": message}


def check_manifest(theme_dir: Path) -> tuple[dict | None, list[dict]]:
    """Load + schema-validate theme.yaml; return (manifest or None, results)."""
    manifest_path = theme_dir / "theme.yaml"
    if not manifest_path.exists():
        return None, [_fail(f"theme.yaml not found in {config.rel(theme_dir)}")]
    try:
        manifest = config.load_theme(theme_dir)
    except config.ConfigError as e:
        return None, [_fail(str(e))]
    return manifest, [_ok(f"theme.yaml valid (name: {manifest['name']})")]


def check_templates(theme_dir: Path) -> list[dict]:
    """Every required template is present and loads in the sandboxed environment."""
    templates_dir = theme_dir / "templates"
    env = build_html.make_env(templates_dir)
    results: list[dict] = []
    for name in REQUIRED_TEMPLATES:
        if not (templates_dir / name).exists():
            results.append(_fail(f"missing template templates/{name}"))
            continue
        try:
            env.get_template(name)  # parse + compile under the sandbox
        except TemplateError as e:
            results.append(_fail(f"templates/{name}: {e}"))
        else:
            results.append(_ok(f"templates/{name} loads in the sandbox"))
    return results


def check_fonts(theme_dir: Path, manifest: dict) -> list[dict]:
    """Each embedded family has a present file and a permissible, documented license."""
    faces = manifest.get("font_faces") or []
    if not faces:
        return [_note("no embedded fonts declared")]
    meta = {m["family"]: m for m in (manifest.get("fonts_meta") or [])}
    results: list[dict] = []
    families: list[str] = []
    for face in faces:
        if not (theme_dir / "fonts" / face["file"]).exists():
            results.append(_fail(f"font file fonts/{face['file']} not found (family {face['family']!r})"))
        if face["family"] not in families:
            families.append(face["family"])
    for family in families:
        entry = meta.get(family)
        if entry is None:
            results.append(_fail(f"font family {family!r} has no fonts_meta license entry"))
        elif _license_permissible(entry["license"]):
            results.append(_ok(f"font {family!r} licensed {entry['license']}"))
        else:
            results.append(_fail(f"font {family!r} license {entry['license']!r} is not on the permissible allowlist"))
    return results


def lint(theme_dir: Path) -> list[dict]:
    """Run every theme check, returning the flat list of result records."""
    manifest, results = check_manifest(theme_dir)
    results = list(results)
    results += check_templates(theme_dir)
    if manifest is not None:
        results += check_fonts(theme_dir, manifest)
    return results


def _report(theme_dir: Path, results: list[dict]) -> int:
    ui.step(ui.style(f"Linting theme {config.rel(theme_dir)}", "bold"))
    fails = 0
    for r in results:
        if r["level"] == "ok":
            ui.step(f"  ok   {r['message']}")
        elif r["level"] == "note":
            ui.step(f"  note {r['message']}")
        else:
            ui.step(f"  {ui.style('FAIL', 'red')} {r['message']}")
            fails += 1
    ui.step("")
    if fails:
        ui.step(ui.style(f"  {fails} check(s) failed.", "red"))
        return ui.VALIDATION
    ui.step("  Theme lint passed.")
    return ui.OK


def _lint_main(argv: list[str]) -> int:
    ap = ui.command_parser(
        "ladle theme lint",
        "Check a theme against the gallery gate: manifest schema, template sandbox, font licenses.",
        "ladle theme lint default",
    )
    ap.add_argument("theme", help="theme name (bundled) or path to a theme directory")
    args = ap.parse_args(argv)
    theme_dir = config.resolve_theme_dir(args.theme)
    if not theme_dir.is_dir():
        hint = "pass a theme name or a path to a theme dir"
        return ui.die(f"theme not found: {config.rel(theme_dir)}", ui.ERROR, hint=hint)
    return _report(theme_dir, lint(theme_dir))


_SUBCOMMANDS = {"lint": _lint_main}


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        subs = ", ".join(_SUBCOMMANDS)
        ui.step(f"usage: ladle theme <subcommand> [args]\n\nsubcommands: {subs}")
        return ui.OK
    sub = _SUBCOMMANDS.get(argv[0])
    if sub is None:
        return ui.die(
            f"unknown theme subcommand {argv[0]!r}",
            ui.USAGE,
            hint=f"try one of: {', '.join(_SUBCOMMANDS)}",
        )
    return sub(argv[1:])


if __name__ == "__main__":
    sys.exit(main())
