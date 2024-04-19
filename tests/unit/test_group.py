"""Test group features."""

import re

import pytest
from filefinder.format import Format
from filefinder.group import Group, GroupParseError
from hypothesis import example, given
from hypothesis import strategies as st
from util import FormatValue, GroupTest, GroupValue, StFormat, StGroup, form


def assert_grp(spec: str, expected_rgx: str, expected_fmt: str):
    grp = Group(spec, 0)
    assert grp.get_regex() == expected_rgx
    assert grp.fmt.fmt == expected_fmt


@given(ref=StGroup.group())
def test_definition_parsing(ref: GroupTest):
    """Test definitions generated by hypothesis."""
    g = Group(ref.definition, 0)

    assert g.name == ref.name

    # Test flags
    assert g.optional == ref.opt
    assert g.discard == ref.discard

    # Test rgx, format
    if "rgx" in ref:
        assert g.rgx == ref.rgx

        rgx = f"({ref.rgx})"
        if ref.opt:
            rgx += "?"
        assert g.get_regex() == rgx

    if "fmt" in ref:
        assert g.fmt.fmt == ref.fmt

    if "bool" in ref and "rgx" not in ref:
        assert ref.bool_elts is not None
        a, b = ref.bool_elts
        assert g.options == (a, b)
        assert g.rgx == f"{a}|{b}"


@given(ab=StGroup.bool_elts())
@example(ab=("foo", ""))
def test_bool_regex(ab):
    """Test bool spec generated by hypothesis."""
    a, b = ab
    rgx_a, rgx_b = (re.escape(x) for x in ab)
    grp = Group(f"name:bool={a}:{b}", 0)
    assert grp.rgx == f"{rgx_a}|{rgx_b}"
    assert grp.options == (b, a)

    grp = Group(f"name:bool={a}", 0)
    assert grp.rgx == f"{rgx_a}|"
    assert grp.options == ("", a)


@given(ref=StGroup.group_value(parsable=True))
def test_group_parse_back(ref: GroupValue):
    """Test if a group can parse a value that it formatted."""
    grp = Group(ref.definition, 0)
    assert grp.parse(ref.value_str) == ref.value


@pytest.mark.parametrize(
    "spec",
    [
        # empty
        "",
        # no name
        ":fmt=08d",
        # argument given to flags
        "a:opt=stuff",
        "a:discard=stuff",
        # no argument given to format
        "a:fmt=",
        # properties specified twice
        "a:opt:fmt=02d:opt",
        "a:rgx=foo:rgx=bar",
        "a:opt:rgx=bar:opt:opt",
        # wrong
        "a:optional",
        "a:fmt",
    ],
)
def test_bad_definition(spec: str):
    """Test some obvious bad definitions."""
    with pytest.raises(GroupParseError):
        Group(spec, 0)


@pytest.mark.parametrize(
    "name,expected_rgx,expected_fmt",
    [
        ("I", r"(\d+)", "d"),
        ("Y", r"(\d{4})", "04d"),
        ("m", r"(\d\d)", "02d"),
        ("x", r"(\d{4}\d\d\d\d)", "08d"),
        ("X", r"(\d\d\d\d\d\d)", "06d"),
        ("F", r"(\d{4}-\d\d-\d\d)", "s"),
    ],
)
def test_some_default_names(name, expected_rgx, expected_fmt):
    """Test various default names."""
    assert_grp(name, expected_rgx, expected_fmt)


def test_default_overwrite():
    """Test if rgx and fmt overwrite correctly the defaults."""
    assert_grp("Y:rgx=foo", "(foo)", "04d")
    assert_grp("Y:rgx=foo:fmt=s", "(foo)", "s")
    assert_grp("Y:rgx=foo:fmt=s:opt:discard", "(foo)?", "s")
    assert_grp("Y:fmt=08d", "({})".format(Format("08d").generate_expression()), "08d")
    assert_grp("Y:bool=true:false:fmt=s", "(true|false)", "s")


def test_percent_rgx():
    assert_grp("foo:rgx=a-%x", r"(a-\d{4}\d\d\d\d)", "s")
    assert_grp("foo:rgx=%Y.%m.%d", r"(\d{4}.\d\d.\d\d)", "s")
    # escape the percent
    assert_grp("foo:rgx=%Y-100%%", r"(\d{4}-100%)", "s")

    with pytest.raises(KeyError):
        Group("foo:rgx=%e", 0)


@given(ref=StFormat.format_value(kind="dfeE"))
def test_fix_format_number(ref: FormatValue):
    fmt = ref.format_string
    number = ref.value
    g = Group(f"foo:fmt={fmt}", 0)
    g.fix_value(number)
    assert g.fixed_value == number
    assert g.fixed_string == form(fmt, number)
    assert g.fixed_regex == re.escape(form(fmt, number))


@given(a=st.integers(), b=st.integers())
def test_fix_value_consecutive(a: int, b: int):
    g = Group("foo:fmt=d", 0)
    g.fix_value(a)
    assert g.fixed_value == a
    g.unfix()
    assert g.fixed_value is None
    g.fix_value(b)
    assert g.fixed_value == b


@given(ref=StFormat.format_value(kind="s"))
def test_fix_value_string(ref: FormatValue):
    g = Group(f"foo:fmt={ref.format_string}", 0)
    g.fix_value(ref.value)
    assert g.fixed_value == g.fixed_string == g.fixed_regex == ref.value
    assert g.get_regex() == f"({ref.value})"


def test_fix_value_bool():
    g = Group("foo:bool=opt1:opt2", 0)
    g.fix_value(True)
    assert g.fixed_string == g.fixed_regex == "opt1"
    g.fix_value(False)
    assert g.fixed_string == g.fixed_regex == "opt2"

    with pytest.raises(ValueError):
        g = Group("Y", 0)
        g.fix_value(True)


@given(
    elements=st.lists(st.integers(), min_size=1),
    fmt=StFormat.format(kind="d").map(lambda ref: ref.format_string),
)
def test_fix_value_integer_list(elements: list[int], fmt: str):
    g = Group(f"foo:fmt={fmt}", 0)
    g.fix_value(elements)
    formatted_elts = [form(fmt, e) for e in elements]
    assert g.fixed_regex == ("|".join(re.escape(e) for e in formatted_elts))
    assert g.fixed_string == formatted_elts[0]

    with pytest.raises(ValueError):
        g.fix_value([])
