"""General utilities for testing."""

import sys
from typing import Any, Protocol, TypeVar

import hypothesis.strategies as st

from filefinder.group import Group

MAX_CODEPOINT = 1024
MAX_TEXT_SIZE = 32

if sys.platform in ["win32", "cygwin"]:
    FORBIDDEN_CHAR = set('<>:;"\\|?.*')
elif sys.platform == "darwin":
    FORBIDDEN_CHAR = set(":;")
else:
    FORBIDDEN_CHAR = set()


T = TypeVar("T")


class Drawer(Protocol):
    def __call__(self, __strat: st.SearchStrategy[T]) -> T: ...


def assert_fixed(group: Group, value: Any, string: str | list[str], regex: str):
    assert group.fixed
    assert group.fixed_value == value
    assert group.fixed_string == string
    assert group.fixed_regex == regex


def assert_unfixed(group: Group):
    assert group.fixed_value is None
    assert group.fixed_string is None
    assert group.fixed_regex is None


def build_exclude(
    exclude: set[str] | None = None,
    for_pattern: bool = False,
    for_filename: bool = False,
) -> set[str]:
    """Build a set of characters to exclude.

    Parameters
    ----------
    exclude
        Base set of characters to exclude. Default (None) is empty.
    for_pattern
        If True, exclude group-related characters `%()`.
    for_filename
        If True, exclude characters forbidden in filenames on current platform. Also
        exclude the filefinder default folder separator '/', whatever the platform.
    """
    if exclude is None:
        exclude = set()
    if for_pattern:
        exclude |= set("%()")
    if for_filename:
        exclude |= FORBIDDEN_CHAR
        exclude.add("/")
    return exclude


def form(fmt: str, value: Any) -> str:
    """Format a value from a format string.

    The format does not include the starting ':'.
    """
    return f"{{:{fmt}}}".format(value)
