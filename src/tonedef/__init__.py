# This file makes the folder a proper Python package and controls
# what you get when you do `from tonedef import ...`

from importlib.metadata import PackageNotFoundError, version

__all__ = ["__version__"]

# Read the version from installed package metadata
# pyproject.toml stays the single source of truth
try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"
