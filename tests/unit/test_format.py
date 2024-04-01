"""Test regex generation from format string.

Systematically generate formats, and test some number.

'e' formats are not tested for parsing, since it needs to account for the
number of significant digits (and the testing code would be more prone to
failure than the actual parsing code...).
"""

import re
import typing as t

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


def assert_format(value: t.Any, fmt: FormatAbstract):
    """Check if a value formatted by Format is parsed by Format."""
    string = fmt.format(value)
    pattern = fmt.generate_expression()
    m = re.fullmatch(pattern, string)
    assert (
        m is not None
    ), f"No match. Format '{fmt.fmt}'. Pattern '{pattern}'. String '{string}'"


def assert_parse_int(number: int, fmt: FormatInteger):
    """Assert Format parse correctly a value it has formatted."""
    string = fmt.format(number)
    parsed = fmt.parse(string)
    assert (
        number == parsed
    ), f"Not parsed. Format '{fmt.fmt}'. Number '{number}'. Parsed '{parsed}'"


def assert_parse_float(number: float, fmt: FormatFloat, precision: str, kind="f"):
    """Assert Format parse correctly a float value it has formatted.

    Has to deal with precision here,
    """
    string_ref = f"{{:{'.6' if precision == '' else precision}{kind}}}".format(number)
    parsed_ref = float(string_ref)

    string = fmt.format(number)
    parsed = fmt.parse(string)
    assert (
        parsed_ref == parsed
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
    """Test integer formats (type d)."""
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + "d"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    assert_format(number, fmt)
    assert_parse_int(number, fmt)


@pytest.mark.parametrize("align", align)
@pytest.mark.parametrize("sign", sign)
@pytest.mark.parametrize("alt", alt)
@pytest.mark.parametrize("zero", zero)
@pytest.mark.parametrize("grouping", grouping)
@given(
    fill=fill,
    width=width,
    precision=precision,
    number=st.floats(allow_nan=False, allow_infinity=False),
)
def test_format_f(fill, align, sign, alt, zero, grouping, width, precision, number):
    """Test floating point formats (type f)."""
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + precision + "f"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    assert_format(number, fmt)
    assert_parse_float(number, fmt, precision)


@pytest.mark.parametrize("align", align)
@pytest.mark.parametrize("sign", sign)
@pytest.mark.parametrize("alt", alt)
@pytest.mark.parametrize("zero", zero)
@pytest.mark.parametrize("grouping", grouping)
@given(
    fill=fill,
    width=width,
    precision=precision,
    number=st.floats(allow_nan=False, allow_infinity=False),
)
def test_format_e(fill, align, sign, alt, zero, width, grouping, precision, number):
    """Test exponant formats (type e)."""
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + precision + "e"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    assert_format(number, fmt)
    assert_parse_float(number, fmt, precision, kind="e")


# def test_format_s(align, width, value):
#     fmt = Format(align + width + "s")
#     s = fmt.format(value)
#     assert_format(s, fmt)
