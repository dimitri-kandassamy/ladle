"""ladle — build art-directed cookbooks (PDF + EPUB) from markdown recipes."""

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the installed package's metadata, which the build
    # backend fills from pyproject.toml's `version`. No second literal to drift.
    __version__ = version("ladlebook")
except PackageNotFoundError:  # running from a source tree that was never installed
    __version__ = "0.0.0+dev"
