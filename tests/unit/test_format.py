"""Test regex generation from format string.

All possible formats are tested using a mixture of pytest parametrization and
hypothesis (for fill character, width and precision).

For each generated format object, and any number (using hypothesis):
* check that the generated regex match the formatted number
* check that we can parse the number back
"""

import re
import typing as t

import pytest
from filefinder.format import (
    DangerousFormatError,
    Format,
    FormatAbstract,
    FormatError,
    FormatFloat,
    FormatInteger,
)
from hypothesis import given
from hypothesis import strategies as st


def assert_regex_match(value: t.Any, fmt: FormatAbstract):
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


align = ["", "<", ">", "=", "^"]
sign = ["", "+", "-", " "]
alt = ["", "#"]
zero = ["", "0"]
grouping = ["", ",", "_"]
width = st.one_of(st.just(""), st.integers(min_value=0, max_value=256).map(str))
precision = st.one_of(
    st.just(""), st.integers(min_value=0, max_value=64).map(lambda i: f".{i}")
)
fill = st.text(
    alphabet=st.characters(
        codec="utf-8", exclude_characters=["{", "}"], categories=["L", "P", "S"]
    ),
    min_size=0,
    max_size=1,
)


# Start by quick tests where the whole format is generated by hypothesis


@st.composite
def format_d(draw):
    """Return format string for integer."""
    align_ = draw(st.sampled_from(align))
    sign_ = draw(st.sampled_from(sign))
    zero_ = draw(st.sampled_from(zero))
    grouping_ = draw(st.sampled_from(grouping))
    width_ = draw(width)

    fmt = draw(fill) + align_ if align_ else ""
    fmt += sign_ + zero_ + width_ + grouping_ + "d"
    return fmt


@given(fmt=format_d(), number=st.integers())
def test_format_d_quick(fmt: str, number: int):
    """Test integer format."""
    try:
        f = t.cast(FormatInteger, Format(fmt))
    except DangerousFormatError:
        return
    assert_regex_match(number, f)
    assert_parse_int(number, f)


@st.composite
def format_float(draw) -> tuple[str, ...]:
    """Return float format, and the precision and type components."""
    align_ = draw(st.sampled_from(align))
    sign_ = draw(st.sampled_from(sign))
    alt_ = draw(st.sampled_from(alt))
    zero_ = draw(st.sampled_from(zero))
    grouping_ = draw(st.sampled_from(grouping))
    width_ = draw(width)
    precision_ = draw(precision)
    kind_ = draw(st.sampled_from(["f", "e", "E"]))

    fmt = draw(fill) + align_ if align_ else ""
    fmt += sign_ + alt_ + zero_ + width_ + grouping_ + precision_ + kind_
    return (fmt, precision_, kind_)


@given(input=format_float(), number=st.integers())
def test_format_float_quick(input: tuple[str, ...], number: int):
    """Test float format."""
    fmt, precision, kind = input
    try:
        f = t.cast(FormatFloat, Format(fmt))
    except DangerousFormatError:
        return
    assert_regex_match(number, f)
    assert_parse_float(number, f, precision, kind)


# We continue with formats generated systematically
# This can take some time


@pytest.mark.parametrize("align", align)
@pytest.mark.parametrize("sign", sign)
@pytest.mark.parametrize("zero", zero)
@pytest.mark.parametrize("grouping", grouping)
@given(fill=fill, width=width, number=st.integers())
def test_format_d(fill, align, sign, zero, width, grouping, number):
    """Test integer formats (type d)."""
    format_string = fill + align if align else ""
    format_string += sign + zero + width + grouping + "d"

    try:
        fmt = Format(format_string)
    except DangerousFormatError:
        return
    assert_regex_match(number, fmt)
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
def test_format_float(fill, align, sign, alt, zero, grouping, width, precision, number):
    """Test float formats (type f and e)."""
    format_string = fill + align if align else ""
    format_string += sign + alt + zero + width + grouping + precision

    for kind in "feE":
        try:
            fmt = Format(format_string + kind)
        except DangerousFormatError:
            return
        assert_regex_match(number, fmt)
        assert_parse_float(number, fmt, precision, kind)


@pytest.mark.parametrize("align", align)
@given(
    fill=fill,
    width=width,
    value=st.text(alphabet=st.characters(exclude_categories=["C"])),
)
def test_format_s(fill, align, width, value):
    """Test string format."""
    format_string = fill + align if align else ""
    format_string += width + "s"

    if align == "=":
        with pytest.raises(FormatError):
            fmt = Format(format_string)
        return

    fmt = Format(format_string)
    s = fmt.format(value)
    assert_regex_match(s, fmt)
