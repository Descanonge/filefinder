"""Test main features."""

import itertools
import logging
import os
from datetime import datetime, timedelta
from os import path

import pytest
from filefinder import Finder
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from pyfakefs.fake_filesystem import FakeFilesystem
from util import (
    MAX_CODEPOINT,
    MAX_TEXT_SIZE,
    Pattern,
    PatternValue,
    PatternValues,
    StPattern,
)

log = logging.getLogger(__name__)


def assert_pattern(pattern: str, regex: str):
    """Assert that `pattern` will generate `regex`."""
    finder = Finder("", pattern)
    assert finder.get_regex() == regex


@given(ref=StPattern.pattern(separate=False))
def test_group_names(ref: Pattern):
    """Test that we retain group names, and the correct number of groups."""
    f = Finder("", ref.pattern)
    assert f.n_groups == len(f.groups) == len(ref.groups)

    for i in range(f.n_groups):
        assert f.groups[i].name == ref.groups[i].name


@given(ref=StPattern.pattern(separate=False))
def test_get_groups(ref: Pattern):
    """Test that Finder.get_groups return the correct indices given a group name."""
    f = Finder("", ref.pattern)

    names = set(g.name for g in ref.groups)

    for name in names:
        indices_ref = [i for i, g in enumerate(ref.groups) if g.name == name]
        indices = [g.idx for g in f.get_groups(name)]
        assert indices_ref == indices


@given(
    ref=StPattern.pattern(separate=False),
    root=st.text(
        alphabet=st.characters(
            exclude_categories=["C"],
            max_codepoint=MAX_CODEPOINT,
        ),
        max_size=MAX_TEXT_SIZE,
    ),
)
def test_finder_str(ref: Pattern, root: str):
    f = Finder(root, ref.pattern)
    lines = str(f).splitlines()
    assert lines[0] == f"root: {root}"
    assert lines[1] == f"pattern: {ref.pattern}"
    assert lines[-1] == "not scanned"


@given(
    ref=StPattern.pattern_value(
        separate=True, parsable=True, ignore=["opt"], for_filename=True
    )
)
def test_match_filename_values(ref: PatternValue):
    """Test values in a matched filename are correctly parsed.

    Pattern is generated automatically with appropriate values (and formatted values).
    The reference filename is constructed from the pattern segments and the formatted
    values that were drawn.

    For each group that has a definition allowing to generate a value, we check that
    filefinder has correctly parsed the value back.
    If the group has no discard flag, we also test Matches.__getitem__.
    """
    # reference filename
    f = Finder("", ref.pattern)
    matches = f.find_matches(ref.filename)
    assert matches is not None

    # Correct number of matches
    assert len(matches) == len(ref.groups)

    for i, grp in enumerate(ref.groups):
        assert matches.get_value(key=i, parse=True, keep_discard=True) == grp.value
        assert matches.get_value(key=i, parse=False, keep_discard=True) == grp.value_str
        # Test shortcut
        if not grp.discard:
            assert matches[i] == grp.value
        else:
            with pytest.raises(KeyError):
                _ = matches[i]


@given(
    ref=StPattern.pattern_value(
        separate=True, parsable=True, ignore=["opt"], for_filename=True
    )
)
def test_matches_str(ref: PatternValue):
    """Check Match(es).__str__ do not raise."""
    # reference filename
    f = Finder("", ref.pattern)
    matches = f.find_matches(ref.filename)
    assert matches is not None

    str(matches)
    repr(matches)
    for m in matches.matches:
        str(m)
        repr(m)


@given(ref=StPattern.pattern_value(for_filename=True))
def test_make_filename_by_str(ref: PatternValue):
    """Test filename creation using string as fixes.

    Check fixing by value is conserved.
    Check by index. Only run by name (cannot check the expected filename).
    """
    f = Finder("/base/", ref.pattern)
    fixes = {i: grp.value_str for i, grp in enumerate(ref.groups)}
    # we won't check the output for those
    fixes_by_name = {grp.name: grp.value_str for grp in ref.groups}
    assert f.make_filename(fixes, relative=True) == ref.filename
    f.make_filename(fixes_by_name)

    if f.n_groups > 0:
        with pytest.raises(ValueError):
            f.make_filename()


# No s-type formats, strings are not considered values by filefinder
@given(ref=StPattern.pattern_value(for_filename=True, fmt_kind="dfeE"))
def test_make_filename_by_val(ref: PatternValue):
    """Test filename creation using values as fixes."""
    f = Finder("/base/", ref.pattern)
    fixes = {i: grp.value_str for i, grp in enumerate(ref.groups)}
    assert f.make_filename(fixes, relative=True) == ref.filename

    if f.n_groups > 0:
        with pytest.raises(ValueError):
            f.make_filename()


@given(
    ref=StPattern.pattern_value(for_filename=True, min_group=1, fmt_kind="dfeE")
    .filter(lambda p: len(set(g.name for g in p.groups)) == len(p.groups))
    .filter(lambda p: all(g.name != "relative" for g in p.groups))
)
def test_make_filename_by_val_by_name(ref: PatternValue):
    """Test filename creation fixing values by group name.

    Separate test function to make sure all names are differents, otherwise
    group.fix_value might have different output despite having the same name.
    Also avoid keyword name relative.
    """
    f = Finder("/base/", ref.pattern)
    fixes_by_name = {grp.name: grp.value for grp in ref.groups}
    assert f.make_filename(**fixes_by_name, relative=True) == ref.filename


@given(ref=StPattern.pattern_value(for_filename=True, fmt_kind="dfeE"))
def test_make_filename_by_fix(ref: PatternValue):
    """Test filename creating with prior value fixing.

    All formatted values are fixed by index. Filename is checked against expected value.
    Groups are unfixed, and refixed by name before testing if filename creation runs
    (no value check against expected filename).
    """
    f = Finder("/base/", ref.pattern)
    fixes = {i: grp.value_str for i, grp in enumerate(ref.groups)}
    # we won't check the output for those
    fixes_by_name = {grp.name: grp.value_str for grp in ref.groups}

    # Fix and check output
    f.fix_groups(fixes, fix_discard=True)
    assert f.make_filename(relative=True) == ref.filename
    # check str/repr
    str(f)
    repr(f)

    # Reset, fix by name and check there is no error.
    f.unfix_groups()
    f.fix_groups(fixes_by_name, fix_discard=True)
    f.make_filename()


@given(ref=StPattern.pattern_value(for_filename=True, min_group=2, fmt_kind="dfeE"))
def test_make_filename_half_by_fix(ref: PatternValue):
    """Test filename creating with prior value fixing (not all groups).

    Same as previous, but half groups are fixed, and second half is given on
    make_filename call. Formatted values are fixed by index.
    """
    f = Finder("/base/", ref.pattern)
    n_fix = int(f.n_groups / 2)
    f.fix_groups({i: ref.groups[i].value_str for i in range(n_fix)}, fix_discard=True)

    # As is, not everything is fixed
    with pytest.raises(ValueError):
        f.make_filename()

    result = f.make_filename(
        {i: ref.groups[i].value_str for i in range(n_fix, f.n_groups)}, relative=True
    )
    assert result == ref.filename


@pytest.mark.parametrize("pattern", ["ab%(foo:fmt=d)", "ab%(foo:rgx=.*)"])
def test_wrong_filename(pattern: str):
    """Test obviously wrong filenames that won't match.

    Not sure if there is a way to generate wrong filenames in the most general case.
    """
    f = Finder("", pattern)
    assert f.find_matches("bawhatever") is None


def test_group_parenthesis():
    """Test if parenthesis are correctly matched in group definitions.

    Test if unbalanced parentheses in group def raise.
    Test if adding a group in regex causes issues.
    """

    def test(pattern: str):
        Finder("", pattern)

    test("0_%(normal_defintion:fmt=d)")
    test("0_%(paren(in_name):fmt=0d)")
    test("0_%(paren_in_bool:bool=(opt1):opt2)")
    test("0_%(paren_in_rgx:rgx=(?:barr))")  # note non matching to be legal

    for pattern in [
        "0_%(unbalanced(:fmt=d)",
        "0_%(unbalanced:rgx=(())",
        "0_%(unbalanced:bool=()",
    ]:
        with pytest.raises(ValueError):
            test(pattern)

    # legal: non-capturing group
    f = Finder("", "0_%(paren_in_rgx:rgx=(?:barr))")
    assert f.find_matches("0_barr") is not None
    # illegal: additional capturing group
    f = Finder("", "0_%(paren_in_rgx:rgx=(barr))")
    with pytest.raises(IndexError):
        f.find_matches("0_barr")


def test_custom_regex():
    """Test that a custom regex is conserved.

    Tested systematically for groups in test_group.test_random_definitions.
    Here with test that it still works at the Finder level.
    """
    assert_pattern("test_%(Y:rgx=[a-z]*?)", "test_([a-z]*?)")
    assert_pattern("test_%(Y:fmt=d:rgx=[a-z]*?)", "test_([a-z]*?)")


def test_format_regex():
    """Test that the correct regex is generated from a format string.

    Tested systematically for groups in test_group.test_random_definitions.
    Here with test that it still works at the Finder level.
    """
    assert_pattern("test_%(Y:fmt=d)", r"test_(-?\d+)")
    assert_pattern("test_%(Y:fmt=a>5d)", r"test_(a*-?\d+)")
    assert_pattern("test_%(Y:fmt=a<5d)", r"test_(-?\d+a*)")
    assert_pattern("test_%(Y:fmt=a^5d)", r"test_(a*-?\d+a*)")
    assert_pattern("test_%(Y:fmt=05.3f)", r"test_(-?0*\d+\.\d{3})")
    assert_pattern("test_%(Y:fmt=+05.3f)", r"test_([+-]0*\d+\.\d{3})")
    assert_pattern("test_%(Y:fmt=.2e)", r"test_(-?\d\.\d{2}e[+-]\d{2,3})")
    assert_pattern("test_%(Y:fmt=.2E)", r"test_(-?\d\.\d{2}E[+-]\d{2,3})")


# It is possible to add random files, but it is difficult to ensure they will not
# match... It is easy to find counter examples.
@settings(
    suppress_health_check=[HealthCheck.function_scoped_fixture],
    deadline=None,
)
@given(ref=StPattern.pattern_values(for_filename=True, min_group=1, parsable=False))
def test_file_scan(fs: FakeFilesystem, ref: PatternValues):
    """Test that we scan files generated randomly.

    Each pattern comes with lists of values for each group to generate multiple
    filenames.
    Groups are separated by at least one character to avoid ambiguous parsing (for
    instance two consecutive integers cannot be separated).
    """
    try:
        fs.root_dir.remove_entry("data")
    except KeyError:
        pass
    basedir = path.join(fs.root_dir_name, "data")
    fs.create_dir(basedir)

    files = list(ref.filenames)
    files = list(set(files))
    files.sort()
    for f in files:
        fs.create_file(path.join(basedir, f))

    log.info("pattern: %s", ref.pattern)
    log.info("n_files: %d", len(files))
    finder = Finder(basedir, ref.pattern)
    assert len(finder.files) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref

    # Check str/repr
    lines = str(finder).splitlines()
    assert lines[-1] == f"scanned: found {len(files)} files"


def test_file_scan_manual(fs):
    dates = [datetime(2000, 1, 1) + i * timedelta(days=15) for i in range(50)]
    params = [-1.5, 0.0, 1.5]
    options = [False, True]

    datadir = path.join(fs.root_dir_name + "data")
    fs.create_dir(datadir)
    files = []
    for d, p, o in itertools.product(dates, params, options):
        filename = "{}{}test_{}_{:.1f}{}.ext".format(
            d.year, path.sep, d.strftime("%F"), p, "_yes" if o else ""
        )
        files.append(filename)
        fs.create_file(path.join(datadir, filename))
    files.sort()

    for i in range(20):
        fs.create_file(path.join(datadir, f"invalid_files_{i}.ext"))

    finder = Finder(
        datadir,
        "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
    )
    assert len(finder.files) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref


def test_file_scan_nested(fs):
    """Test simple case of nested filenames output."""

    def make_filename(date: datetime, param: float, option: bool) -> str:
        filename = (
            f"{date.year}{os.sep}test"
            f"_{date.strftime('%Y-%m-%d')}"
            f"_{param:.1f}{'_yes' if option else ''}.ext"
        )
        return filename

    def make_filenames(
        dates: list[datetime], params: list[float], options: list[bool]
    ) -> list[str]:
        files = []
        for date, param, option in itertools.product(dates, params, options):
            files.append(make_filename(date, param, option))
        files.sort()
        return files

    dates = [datetime(2000, 1, 1) + i * timedelta(days=15) for i in range(50)]
    params = [-1.5, 0.0, 1.5]
    options = [False, True]

    datadir = path.join(fs.root_dir_name + "data")
    fs.create_dir(datadir)
    files = make_filenames(dates, params, options)
    for f in files:
        fs.create_file(path.join(datadir, f))

    for i in range(20):
        fs.create_file(path.join(datadir, f"invalid_files_{i}.ext"))

    finder = Finder(
        datadir,
        "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
    )
    assert len(finder.files) == len(files)

    # Nest by param
    nested_param = finder.get_files(relative=True, nested=["param"])
    assert len(nested_param) == len(params)
    for param_ref, nested_inner in zip(params, nested_param):
        nest_files_ref = make_filenames(dates, [param_ref], options)
        assert len(nested_inner) == len(nest_files_ref)
        for f, f_ref in zip(nested_inner, nest_files_ref):
            assert f == f_ref

    # Nest by year
    nested_y = finder.get_files(relative=True, nested=["Y"])
    years = sorted(list(set(d.year for d in dates)))
    assert len(nested_y) == len(years)
    for year_ref, nested_inner in zip(years, nested_y):
        nested_inner_ref = make_filenames(
            [d for d in dates if d.year == year_ref], params, options
        )
        assert len(nested_inner) == len(nested_inner_ref)
        for f, f_ref in zip(nested_inner, nested_inner_ref):
            assert f == f_ref

    # Nest by option then param
    nested_option = finder.get_files(relative=True, nested=["option", "param"])
    assert len(nested_option) == len(options)
    for option_ref, nested_param in zip(options, nested_option):
        assert len(nested_param) == len(params)
        for param_ref, nested_inner in zip(params, nested_param):
            assert len(nested_inner) == len(dates)
            nested_inner_ref = make_filenames(dates, [param_ref], [option_ref])
            for f, f_ref in zip(nested_inner, nested_inner_ref):
                assert f == f_ref

    # Nest by everything
    nested_param = finder.get_files(
        relative=True, nested=["param", "option", "Y", "m", "d"]
    )
    assert len(nested_param) == len(params)
    for param_ref, nested_option in zip(params, nested_param):
        assert len(nested_option) == len(options)
        for option_ref, nested_y in zip(options, nested_option):
            years = sorted(list(set(d.year for d in dates)))
            assert len(nested_y) == len(years)
            for y_ref, nested_m in zip(years, nested_y):
                dates_y = [d for d in dates if d.year == y_ref]
                months = sorted(list(set(d.month for d in dates_y)))
                assert len(nested_m) == len(months)
                for m_ref, nested_d in zip(months, nested_m):
                    dates_m = [d for d in dates_y if d.month == m_ref]
                    days = sorted(list(set(d.day for d in dates_m)))
                    assert len(nested_d) == len(dates_m)
                    for d_ref, nested_inner in zip(days, nested_d):
                        assert len(nested_inner) == 1
                        filename = make_filename(
                            datetime(y_ref, m_ref, d_ref), param_ref, option_ref
                        )
                        assert nested_inner[0] == filename


def test_opt_directory(fs):
    """Test having a directory separator in an optional group."""
    datadir = path.sep + "alpha"
    fs.create_dir(datadir)

    files = [
        "0.txt",
        f"a{os.sep}1.txt",
        f"b{os.sep}2.txt",
        f"a{os.sep}c{os.sep}3.txt",
        f"b{os.sep}d{os.sep}4.txt",
    ]
    files.sort()
    for f in files:
        fs.create_file(path.join(datadir, f))

    finder = Finder(
        datadir,
        "%(folder:rgx=[a-z]/:opt)%(folder:rgx=[a-z]/:opt)%(param:fmt=d).txt",
        scan_everything=True,
    )
    assert len(finder.get_files()) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref
