"""Test main features."""

import logging
import os
import sys
from datetime import datetime
from os import path
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from util import (
    MAX_CODEPOINT,
    MAX_TEXT_SIZE,
    FilesDefinition,
    FilesDefinitionAuto,
    PatternSpecs,
    PatternValue,
    PatternValues,
    StPattern,
    TmpDirTest,
    time_segments,
)

from filefinder import Finder
from filefinder.util import datetime_to_value, name_to_date

log = logging.getLogger(__name__)


def assert_pattern(pattern: str, regex: str):
    """Assert that `pattern` will generate `regex`."""
    finder = Finder("", pattern)
    assert finder.get_regex() == regex


class TestFinderStructure:
    @given(ref=StPattern.pattern(separate=False))
    def test_group_names(self, ref: PatternSpecs):
        """Test that we retain group names, and the correct number of groups."""
        f = Finder("", ref.pattern)
        assert f.n_groups == len(f.groups) == len(ref.groups)

        ref_names = [grp.name for grp in ref.groups]

        for i in range(f.n_groups):
            assert f.groups[i].name == ref_names[i]

        assert f.get_group_names() == set(ref_names)

        # fix even groups
        fixed = set()
        for grp in ref.groups[::2]:
            if grp.discard:
                continue
            f.fix_group(grp.name, "a")
            fixed.add(grp.name)
        assert f.get_group_names(fixed=True) == fixed

        f.unfix_groups()

        # fix even groups even when discarded
        for i in range(0, f.n_groups, 2):
            f.fix_group(i, "a", fix_discard=True)
        assert f.get_group_names(fixed=True) == set(ref_names[::2])

    @given(ref=StPattern.pattern(separate=False))
    def test_get_groups(self, ref: PatternSpecs):
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
    def test_finder_repr(self, ref: PatternSpecs, root: str):
        f = Finder(root, ref.pattern)
        lines = repr(f).splitlines()
        assert lines[0] == "Finder"
        assert lines[1] == f"root: {root}"
        assert lines[2] == f"pattern: {ref.pattern}"
        assert lines[-1] == "not scanned"

    def test_group_parenthesis(self):
        """Test if parenthesis are correctly matched in group definitions.

        Test if unbalanced parentheses in group def raise.
        Test if adding a group in regex causes issues.
        """

        def test(pattern: str):
            Finder("", pattern)

        test("0_%(normal_defintion:fmt=d)")
        test("0_%(paren(in_name):fmt=0d)")
        test("0_%(paren_in_bool:bool=(opt1):opt2)")
        test("0_%(paren_in_rgx:rgx=(?:barr))")

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


class TestFinderRegex:
    def test_custom_regex(self):
        """Test that a custom regex is conserved.

        Tested systematically for groups in test_group.test_random_definitions.
        Here with test that it still works at the Finder level.
        """
        assert_pattern("test_%(Y:rgx=[a-z]*?)", "test_([a-z]*?)")
        assert_pattern("test_%(Y:fmt=d:rgx=[a-z]*?)", "test_([a-z]*?)")

    def test_format_regex(self):
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


class TestFixDate:
    @given(segments=time_segments(), date=st.datetimes())
    def test_fix_date(self, segments: list[str], date: datetime):
        group_names = segments[1::2]
        for i, name in enumerate(group_names):
            segments[2 * i + 1] = f"%({name})"
        pattern = "".join(segments).replace("/", os.sep)
        finder = Finder("", pattern)

        finder.fix_group("date", date)
        # check with dedicated function (untested as of yet)
        for name in group_names:
            value = datetime_to_value(date, name)
            for grp in finder.get_groups(name):
                assert grp.fixed_value == value
        # check by hand for simple cases
        for name in set(group_names) & set("YmdHMS"):
            for grp in finder.get_groups(name):
                for elt in name_to_date[name]:
                    assert grp.fixed_value == getattr(date, elt)

    def test_fix_date_wrong(self):
        f = Finder("", "%(Y).ext")
        with pytest.raises(TypeError):
            f.fix_group("date", 1)
        with pytest.raises(TypeError):
            f.fix_group("date", "2010/05/12")
        with pytest.raises(TypeError):
            f.fix_group("date", [datetime(2012, 6, 1)])

    def test_fix_date_collateral(self):
        f = Finder("", "%(Y)/%(Y)%(m)%(d)-%(X)_%(param:fmt=.2f)%(option:bool=_yes).ext")
        f.fix_group("date", datetime(2015, 3, 14, 12, 59, 32))
        for name in "YmdX":
            for grp in f.get_groups(name):
                assert grp.fixed
        for name in ["param", "option"]:
            for grp in f.get_groups(name):
                assert not grp.fixed

        f.fix_groups(option=True)
        f.unfix_groups("date")
        for name in list("YmdX") + ["param"]:
            for grp in f.get_groups(name):
                assert not grp.fixed
        for grp in f.get_groups("option"):
            assert grp.fixed

    def test_fix_date_no_firstclass(self):
        f = Finder("", "%(Y)/%(Y)%(m)%(d)-%(X)_%(param:fmt=.2f)%(option:bool=_yes).ext")
        f.date_is_first_class = False
        with pytest.raises(IndexError):
            f.fix_group("date", datetime(2015, 3, 14, 12, 59, 32))

        f = Finder("", "%(Y)/%(Y)%(m)%(d)-%(X)_%(date:fmt=.2f).ext")
        f.date_is_first_class = False
        f.fix_group("date", 5.0)
        for name in "YmdX":
            for grp in f.get_groups(name):
                assert not grp.fixed
        for grp in f.get_groups("date"):
            assert grp.fixed

        f.fix_groups(Y=2050)
        f.unfix_groups("date")
        for name in "mdX":
            for grp in f.get_groups(name):
                assert not grp.fixed
        for grp in f.get_groups("Y"):
            assert grp.fixed


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


class TestMakeFilename:
    @given(ref=StPattern.pattern_value(for_filename=True))
    def test_by_str(self, ref: PatternValue):
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
    def test_by_val(self, ref: PatternValue):
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
    def test_by_val_by_name(self, ref: PatternValue):
        """Test filename creation fixing values by group name.

        Separate test function to make sure all names are differents, otherwise
        group.fix_value might have different output despite having the same name.
        Also avoid keyword name relative.
        """
        f = Finder("/base/", ref.pattern)
        fixes_by_name = {grp.name: grp.value for grp in ref.groups}
        assert f.make_filename(**fixes_by_name, relative=True) == ref.filename

    @given(ref=StPattern.pattern_value(for_filename=True, fmt_kind="dfeE"))
    def test_by_fix(self, ref: PatternValue):
        """Test filename creating with prior value fixing.

        All formatted values are fixed by index. Filename is checked against expected
        value. Groups are unfixed, and refixed by name before testing if filename
        creation runs (no value check against expected filename).
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
    def test_half_by_fix(self, ref: PatternValue):
        """Test filename creating with prior value fixing (not all groups).

        Same as previous, but half groups are fixed, and second half is given on
        make_filename call. Formatted values are fixed by index.
        """
        f = Finder("/base/", ref.pattern)
        n_fix = int(f.n_groups / 2)
        f.fix_groups(
            {i: ref.groups[i].value_str for i in range(n_fix)}, fix_discard=True
        )

        # As is, not everything is fixed
        with pytest.raises(ValueError):
            f.make_filename()

        result = f.make_filename(
            {i: ref.groups[i].value_str for i in range(n_fix, f.n_groups)},
            relative=True,
        )
        assert result == ref.filename


@pytest.mark.parametrize("pattern", ["ab%(foo:fmt=d)", "ab%(foo:rgx=.*)"])
def test_wrong_filename(pattern: str):
    """Test obviously wrong filenames that won't match.

    Not sure if there is a way to generate wrong filenames in the most general case.
    """
    f = Finder("", pattern)
    assert f.find_matches("bawhatever") is None


class TestFileScan(TmpDirTest):
    # It is possible to add random files, but it is difficult to ensure they will not
    # match... It is easy to find counter examples.
    # For Windows and Mac, they fail on lots of cases a priori because of the weird
    # filenames generated through hypothesis. Linux does not mind though.
    # @pytest.mark.skipif(
    #     sys.platform != "linux",
    #     reason="Windows and MacOS have too much quirks to make it work easily.",
    # )
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
    )
    @given(ref=StPattern.pattern_values(for_filename=True, min_group=1, parsable=False))
    def test_random(self, tmp_path: Path, ref: PatternValues):
        """Test that we scan files generated randomly.

        Each pattern comes with lists of values for each group to generate multiple
        filenames.
        Groups are separated by at least one character to avoid ambiguous parsing (for
        instance two consecutive integers cannot be separated).
        """
        fd = FilesDefinition(tmp_path)
        datadir = "data"
        fd.create_dir(datadir)

        files = list(ref.filenames)
        files = list(set(files))
        files.sort()
        on_disk = []
        for f in files:
            try:
                fullname = fd.create_file(path.join(datadir, f))
            except Exception:
                pass
            else:
                if path.exists(fullname):
                    on_disk.append(f)

        log.info("pattern: %s", ref.pattern)
        log.info("n_files: %d", len(on_disk))
        finder = Finder(fd.get_absolute(datadir), ref.pattern)
        assert len(finder.files) == len(on_disk)
        for f, f_ref in zip(finder.get_files(relative=True), on_disk, strict=False):
            assert f == f_ref

        # Check str/repr
        lines = repr(finder).splitlines()
        assert lines[-1] == f"scanned: found {len(files)} files"

    def test_manual(self, tmp_path: Path):
        fd = FilesDefinitionAuto(tmp_path, create=True)
        for i in range(20):
            fd.create_file(path.join(fd.datadir, f"invalid_files_{i}.ext"))

        finder = Finder(
            fd.get_absolute(fd.datadir),
            "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
        )
        assert len(finder.files) == len(fd.files)
        for f, f_ref in zip(finder.get_files(relative=True), fd.files, strict=False):
            assert f == f_ref

    def test_opt_directory(self, tmp_path: Path):
        """Test having a directory separator in an optional group."""
        fd = FilesDefinition(tmp_path)
        datadir = "data"
        fd.create_dir(datadir)

        files = [
            "0.txt",
            f"a{os.sep}1.txt",
            f"b{os.sep}2.txt",
            f"a{os.sep}c{os.sep}3.txt",
            f"b{os.sep}d{os.sep}4.txt",
        ]
        files.sort()
        for f in files:
            fd.create_file(path.join(datadir, f))

        finder = Finder(
            fd.get_absolute(datadir),
            "%(folder:rgx=[a-z]/:opt)%(folder:rgx=[a-z]/:opt)%(param:fmt=d).txt",
            scan_everything=True,
        )
        assert len(finder.get_files()) == len(files)
        for f, f_ref in zip(finder.get_files(relative=True), files, strict=False):
            assert f == f_ref


class TestFileScanNested:
    """Test simple case of nested filenames output."""

    fd: FilesDefinitionAuto
    finder: Finder

    def setup_test(self, tmp_path: Path):
        self.fd = FilesDefinitionAuto(tmp_path, create=True)

        for i in range(20):
            self.fd.create_file(path.join(self.fd.datadir, f"invalid_files_{i}.ext"))

        self.finder = Finder(
            self.fd.get_absolute(self.fd.datadir),
            "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
        )
        assert len(self.finder.files) == len(self.fd.files)
        self.finder._void_cache()

        return self.fd.dates, self.fd.params, self.fd.options

    def test_nest_by_param(self, tmp_path: Path):
        dates, params, options = self.setup_test(tmp_path)

        nested_param = self.finder.get_files(relative=True, nested=["param"])
        assert len(nested_param) == len(params)

        for param_ref, nested_inner in zip(params, nested_param, strict=False):
            nest_files_ref = self.fd.make_filenames(dates, [param_ref], options)
            assert len(nested_inner) == len(nest_files_ref)
            for f, f_ref in zip(nested_inner, nest_files_ref, strict=False):
                assert f == f_ref

    def test_nest_by_year(self, tmp_path):
        dates, params, options = self.setup_test(tmp_path)

        nested_y = self.finder.get_files(relative=True, nested=["Y"])
        years = sorted(list(set(d.year for d in dates)))
        assert len(nested_y) == len(years)

        for year_ref, nested_inner in zip(years, nested_y, strict=False):
            nested_inner_ref = self.fd.make_filenames(
                [d for d in dates if d.year == year_ref],
                params,
                options,
            )
            assert len(nested_inner) == len(nested_inner_ref)
            for f, f_ref in zip(nested_inner, nested_inner_ref, strict=False):
                assert f == f_ref

    def test_nest_by_option_param(self, tmp_path):
        dates, params, options = self.setup_test(tmp_path)

        nested_option = self.finder.get_files(relative=True, nested=["option", "param"])
        assert len(nested_option) == len(options)

        for option_ref, nested_param in zip(options, nested_option, strict=False):
            assert len(nested_param) == len(params)
            for param_ref, nested_inner in zip(params, nested_param, strict=False):
                assert len(nested_inner) == len(dates)
                nested_inner_ref = self.fd.make_filenames(
                    dates, [param_ref], [option_ref]
                )
                for f, f_ref in zip(nested_inner, nested_inner_ref, strict=False):
                    assert f == f_ref

    def test_nest_by_everything(self, tmp_path):
        dates, params, options = self.setup_test(tmp_path)

        nested_param = self.finder.get_files(
            relative=True, nested=["param", "option", "Y", "m", "d"]
        )
        assert len(nested_param) == len(params)
        for param_ref, nested_option in zip(params, nested_param, strict=False):
            assert len(nested_option) == len(options)
            for option_ref, nested_y in zip(options, nested_option, strict=False):
                years = sorted(list(set(d.year for d in dates)))
                assert len(nested_y) == len(years)
                for y_ref, nested_m in zip(years, nested_y, strict=False):
                    dates_y = [d for d in dates if d.year == y_ref]
                    months = sorted(list(set(d.month for d in dates_y)))
                    assert len(nested_m) == len(months)
                    for m_ref, nested_d in zip(months, nested_m, strict=False):
                        dates_m = [d for d in dates_y if d.month == m_ref]
                        days = sorted(list(set(d.day for d in dates_m)))
                        assert len(nested_d) == len(dates_m)
                        for d_ref, nested_inner in zip(days, nested_d, strict=False):
                            assert len(nested_inner) == 1
                            filename = self.fd.make_filename(
                                datetime(y_ref, m_ref, d_ref), param_ref, option_ref
                            )
                            assert nested_inner[0] == filename
