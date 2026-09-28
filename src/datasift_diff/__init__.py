"""datasift-diff: compare two datasets by key."""

__version__ = "0.8.0"

from datasift_diff.core import DiffError, diff

__all__ = ["diff", "DiffError", "__version__"]