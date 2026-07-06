# Security Policy

## Supported versions

`ladle` is distributed on PyPI as [`ladlebook`](https://pypi.org/project/ladlebook/).
Security fixes are made against the latest released version. Please upgrade to
the latest release before reporting an issue.

## Reporting a vulnerability

**Please do not open a public issue for security problems.**

Report vulnerabilities privately through GitHub's
[private vulnerability reporting](https://github.com/dimitri-kandassamy/ladle/security/advisories/new)
(Security → Report a vulnerability). If that is unavailable, email
**[dimitri.kandassamy@gmail.com](mailto:dimitri.kandassamy@gmail.com)** with the details.

Please include:

- a description of the issue and its impact,
- the version affected (`ladle --version` or the `ladlebook` version), and
- steps to reproduce, ideally with a minimal `book.yaml` / recipe.

## What to expect

- Acknowledgement of your report within **7 days**.
- An assessment and, if confirmed, a fix and coordinated release.
- Credit in the release notes if you would like it.

## Scope notes

`ladle` runs external tools (pandoc, WeasyPrint, poppler, epubcheck) on local,
author-supplied files to produce a PDF/EPUB. It is not a network service. The
most relevant risks are the handling of untrusted book/recipe input and of the
third-party binaries it invokes — reports in those areas are especially welcome.
