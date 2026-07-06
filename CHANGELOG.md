# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Replaced the example cookbook's recipes (previously attributed to real chefs
  and published sources) with original, neutrally-credited sample recipes.
- Renamed the example book to **The Ladle Kitchen** (was "The Community
  Cookbook"); its directory moved to `examples/the-ladle-kitchen/`.
- Overhauled the README for the public launch: restructured around
  install → usage → build-from-source, added status badges, a hero image, and a
  terminal demo, and tightened the copy and package metadata.

### Added

- Community-health files: `SECURITY.md`, `CHANGELOG.md`, `NOTICE`, issue and
  pull-request templates, and a Dependabot configuration.

### Fixed

- Corrected the `ladle new` usage example in the docs (`--name` is required; the
  bare positional form errors).

### Security

- Hardened CI: pinned all GitHub Actions to commit SHAs, verified the SHA-256 of
  the downloaded pandoc and epubcheck releases, and scoped workflow token
  permissions to least privilege.

## [0.1.0] - 2026-07-05

### Added

- Initial public release: build an art-directed PDF (WeasyPrint) and an
  epubcheck-clean EPUB (pandoc) from a folder of markdown recipes driven by a
  single `book.yaml`.
- `ladle` CLI: `new`, `build`, `html`, `pdf`, `epub`, `illustrations`,
  `assets`, `validate`, `doctor`.
- Swappable themes (bundled `default` theme) with per-book palette/font/label
  overrides.
- Deterministic SVG placeholder illustrations, with automatic preference for a
  raster sibling when real artwork is dropped in.

[Unreleased]: https://github.com/dimitri-kandassamy/ladle/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/dimitri-kandassamy/ladle/releases/tag/v0.1.0
