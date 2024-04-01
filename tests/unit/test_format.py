"""Test regex generation from format string.

Systematically generate formats, and test some number.
To see what formats are tested, see the global variables:
`signs`, `zeros`, `alts`, `aligns`, `grouping`, `widths`, `precisions`.
To see what numbers are tested, see the global variables:
`numbers_d`, `numbers_f`. (For float formats, both numbers list are tested)

For each combination, generate expression from format, and string
from number and format. Check that the regex match.
Check that we parse correctly the number.

'e' formats are not tested for parsing, since it needs to account for the
number of significant digits (and the testing code would be more prone to
failure than the actual parsing code...).
"""

import re

import pytest
from filefinder.format import (
    DangerousFormatError,
    Format,
    FormatAbstract,
    FormatFloat,
    FormatInteger,
)
from hypothesis import given
from hypothesis import strategies as st


def assert_format(string: str, fmt: FormatAbstract):
    pattern = fmt.generate_expression()
    m = re.fullmatch(pattern, string)
    assert (
        m is not None
    ), f"No match. Format '{fmt.fmt}'. Pattern '{pattern}'. String '{string}'"


def assert_parse_int(number: int, string: str, fmt: FormatInteger):
    parsed = fmt.parse(string)
    assert (
        number == parsed
    ), f"Not parsed. Format '{fmt.fmt}'. Number '{number}'. Parsed '{parsed}'"


def assert_parse_float(number: float, string: str, fmt: FormatFloat, precision: str):
    if precision == "":
        decimals = 6
    else:
        decimals = int(precision[-1])
    number = round(number, decimals)

    parsed = fmt.parse(string)
    assert (
        float(number) == parsed
    ), f"Not parsed. Format '{fmt.fmt}'. Number '{number}'. Parsed '{parsed}'"


fill = st.text(
    alphabet=st.characters(
        codec="utf-8", exclude_characters=["{", "}"], categories=["L", "P", "S"]
    ),
    min_size=0,
    max_size=1,
)
align = ["", "<", ">", "=", "^"]
sign = ["", "+", "-", " "]
alt = ["", "#"]
zero = ["", "0"]
grouping = ["", ",", "_"]
width = st.one_of(st.just(""), st.integers(min_value=0, max_value=256).map(str))
precision = st.one_of(
    st.just(""), st.integers(min_value=0, max_value=64).map(lambda i: f".{i}")
)


@pytest.mark.parametrize("align", align)
@pytest.mark.parametrize("sign", sign)
@pytest.mark.parametrize("alt", alt)
@pytest.mark.parametrize("zero", zero)
@pytest.mark.parametrize("grouping", grouping)
@given(fill=fill, width=width, number=st.integers())
def test_format_d(fill, align, sign, alt, zero, width, grouping, number):
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + "d"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    s = fmt.format(number)
    assert_format(s, fmt)

    assert_parse_int(number, s, fmt)


@pytest.mark.parametrize("align", align)
@pytest.mark.parametrize("sign", sign)
@pytest.mark.parametrize("alt", alt)
@pytest.mark.parametrize("zero", zero)
@pytest.mark.parametrize("grouping", grouping)
@given(
    fill=fill,
    width=width,
    precision=precision,
    number=st.integers(),
)
def test_format_f(fill, align, sign, alt, zero, grouping, width, precision, number):
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + precision + "f"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    s = fmt.format(number)
    assert_format(s, fmt)
    assert_parse_float(number, s, fmt, precision)


@pytest.mark.parametrize("align", align)
@pytest.mark.parametrize("sign", sign)
@pytest.mark.parametrize("alt", alt)
@pytest.mark.parametrize("zero", zero)
@pytest.mark.parametrize("grouping", grouping)
@given(
    fill=fill,
    width=width,
    precision=precision,
    number=st.floats(),
)
def test_format_e(fill, align, sign, alt, zero, width, grouping, precision, number):
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + precision + "e"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    s = fmt.format(number)
    assert_format(s, fmt)
    assert_parse_float(number, s, fmt, precision)


# def test_format_s(align, width, value):
#     fmt = Format(align + width + "s")
#     s = fmt.format(value)
#     assert_format(s, fmt)
