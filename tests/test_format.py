"""Test regex generation from format string.

All possible formats are tested using hypothesis (for fill character, width and
precision).

For each generated format object, and any number (using hypothesis):
* check that the generated regex match the formatted number
* check that we can parse the number back
"""

import re
from typing import Any

import pytest
from hypothesis import given
from lib.format_generation import FormatSpecs, StFormat

from filefinder.format import (
    DangerousFormatError,
    Format,
    FormatError,
)


def test_manual() -> None:
    """Some hand-crafted examples."""
    cases = [
        ("d", r"-?\d+"),
        ("+05d", r"[+-]0*\d+"),
        (".1f", r"-?\d+\.\d{1}"),
        ("_<5d", r"-?\d+_*"),  # left align
        ("_<d", r"-?\d+"),  # no align if width is not present
    ]
    for fmt, rgx in cases:
        assert Format(fmt).get_regex() == rgx


@given(*StFormat.format_and_value())
def test_regex_match(specs: FormatSpecs, value: Any) -> None:
    """The regex matches a formatted number."""
    fmt = Format(specs.format_string)

    string = fmt.format(value)
    pattern = fmt.get_regex()
    m = re.fullmatch(pattern, string)
    assert m is not None, f"Could not parse '{string}' with regex '{pattern}'"


@given(*StFormat.format_and_value())
def test_parse_back(specs: FormatSpecs, value: Any) -> None:
    """Round trip: value -> formatted -> parsed."""
    fmt = Format(specs.format_string)

    string = fmt.format(value)
    parsed = fmt.parse(string)
    assert value == parsed


@pytest.mark.parametrize(
    "fmt",
    [">05d", "4>5d", "4<5f", "2^3d", "-^6f"],
)
def test_dangerous_formats(fmt: str) -> None:
    """Test ambiguous formats."""
    with pytest.raises(DangerousFormatError):
        Format(fmt)


@pytest.mark.parametrize(
    "fmt",
    ["#s", "^#5s", "+s", "-s", "5,s"],
)
def test_bad_s_formats(fmt: str) -> None:
    """Test ambiguous formats."""
    with pytest.raises(FormatError):
        Format(fmt)
