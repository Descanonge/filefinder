"""Find files on disk following a given pattern."""

from importlib.metadata import version

from .dates import make_date_groups
from .finder import Finder

__version__ = version("filefinder")

__all__ = ["Finder", "make_date_groups"]
