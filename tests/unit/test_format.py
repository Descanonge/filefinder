"""Test regex generation from format string.

All possible formats are tested using a mixture of pytest parametrization and
hypothesis (for fill character, width and precision).

For each generated format object, and any number (using hypothesis):
* check that the generated regex match the formatted number
* check that we can parse the number back
"""

import re

import pytest
from filefinder.format import (
    DangerousFormatError,
    Format,
    FormatError,
)
from hypothesis import given
from util import FormatValue, StFormat


@given(formatval=StFormat.format_value(safe=True))
def test_regex_match(formatval: FormatValue):
    struct, val = formatval
    fmt = Format(struct.format_string)

    string = fmt.format(val)
    pattern = fmt.generate_expression()
    m = re.fullmatch(pattern, string)
    assert m is not None, f"Could not parse '{string}' with regex '{pattern}'"


@given(formatval=StFormat.format_value(safe=True))
def test_parse_back(formatval: FormatValue):
    struct, val = formatval
    fmt = Format(struct.format_string)

    string = fmt.format(val)
    parsed = fmt.parse(string)
    assert val == parsed


@pytest.mark.parametrize(
    "fmt",
    [">05d", "4>5d", "4<5f", "2^3d", "-^6f"],
)
def test_dangerous_formats(fmt: str):
    """Test ambiguous formats."""
    with pytest.raises(DangerousFormatError):
        Format(fmt)


@pytest.mark.parametrize(
    "fmt",
    ["#s", "^#5s", "+s", "-s", "5,s"],
)
def test_bad_s_formats(fmt: str):
    """Test ambiguous formats."""
    with pytest.raises(FormatError):
        Format(fmt)
