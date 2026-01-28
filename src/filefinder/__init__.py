from importlib.metadata import version

from .finder import Finder

__version__ = version("filefinder")

__all__ = ["Finder"]
