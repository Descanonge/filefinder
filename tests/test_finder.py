"""Test main features."""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import pytest
from lib import assert_fixed, assert_unfixed
from lib.tmp_dir import TmpDirectory, TmpDirectoryExample, date_range

from filefinder import Finder
from filefinder.group import Group
from filefinder.matches import FileMatch, ParseStatus

log = logging.getLogger(__name__)


@dataclass
class PatternExample:
    pattern: str
    names: list[str]


pattern = PatternExample(
    pattern=(
        "A_%(fmt_int:fmt=02d)_%(fmt_str:fmt=s)_%(custom_rgx:rgx=.*)_"
        "%(bool:bool=true.:false.)%(optional:fmt=.1f:pre=_:opt).txt"
    ),
    names=["fmt_int", "fmt_str", "custom_rgx", "bool", "optional"],
)
pattern_double = PatternExample(
    pattern="A-%(fmt_int:fmt=02d)_B-%(fmt_int:fmt=02d)_C-%(other:bool=a:b).txt",
    names=["fmt_int", "fmt_int", "other"],
)
pattern_dates = PatternExample(
    pattern="%(Y)/%(Y)%(m)%(d)-%(j)_%(date2__Y)%(date2__m)%(date2__d)-%(date2__j).txt",
    names=["Y", "Y", "m", "d", "j", "date2__Y", "date2__m", "date2__d", "date2__j"],
)

pattern_examples = [pattern, pattern_double, pattern_dates]


class TestCreation:
    @pytest.mark.parametrize(
        "pattern",
        pattern_examples,
    )
    def test_group_names(self, pattern: PatternExample) -> None:
        """Test that we retain group names, and the correct number of groups."""
        f = Finder("", pattern.pattern)
        assert f.n_groups == len(pattern.names)
        assert f.get_group_names() == set(pattern.names)
        for grp, name in zip(f.groups, pattern.names, strict=True):
            assert grp.name == name

        # fix even groups
        fixed = set()
        for name in pattern.names[::2]:
            f.fix({name: "a"})
            fixed.add(name)
        assert f.get_group_names(fixed=True) == fixed

    def test_get_groups(self) -> None:
        """Test that Finder.get_groups return the correct indices given a group name."""

        def assert_indices(f: Finder, key: str, indices: list[int]) -> None:
            groups = f.get_groups(key)
            assert [g.idx for g in groups] == indices

        f = Finder("", pattern.pattern)
        for i, name in enumerate(pattern.names):
            assert_indices(f, name, [i])

        f = Finder("", pattern_double.pattern)
        assert_indices(f, "fmt_int", [0, 1])
        assert_indices(f, "other", [2])

        f = Finder("", pattern_dates.pattern)
        assert_indices(f, "date", [0, 1, 2, 3, 4])
        assert_indices(f, "date2", [5, 6, 7, 8])

    @pytest.mark.parametrize("pattern", pattern_examples)
    def test_finder_repr(self, pattern: PatternExample) -> None:
        f = Finder("data", pattern.pattern)
        lines = repr(f).splitlines()
        assert lines[0] == "Finder"
        assert lines[1] == "root: data"
        assert lines[2] == f"pattern: {pattern.pattern}"
        assert lines[-1] == "not scanned"

    def test_group_parenthesis(self) -> None:
        """Test if parenthesis are correctly matched in group definitions.

        Test if unbalanced parentheses in group def raise.
        Test if adding a group in regex causes issues.
        """

        def test(pattern: str) -> None:
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

    def test_group_other_delimiters(self) -> None:
        """Test that other group delimiters work."""
        # Using double accolades
        f = Finder("", "0_{{Y}}_{{m}}", group_delimiters=("", "{{", "}}"))
        assert f.get_group_names() == {"Y", "m"}

    def test_regex(self) -> None:
        """Test that the correct regex is generated."""
        f = Finder("", pattern.pattern)
        assert f.get_regex() == (
            r"A_(-?0*\d+)_(.*?\ *)_(.*)_"
            r"(true\.|false\.)((?:_-?\d+\.\d{1})?)\.txt"
        )

        f = Finder("", pattern_dates.pattern)
        rgx = r"(\d{4})(\d\d)(\d\d)\-(\d{3})"
        assert f.get_regex() == rf"(\d{{4}}){re.escape(os.sep)}{rgx}_{rgx}\.txt"


class AssertClear:
    def __init__(self, finder: Finder, clear: bool = True) -> None:
        self.finder = finder
        self.clear = clear

    def __enter__(self) -> None:
        filematch = self.finder.find_matches("A_01_a_b_true._0.5.txt")
        assert filematch is not None
        self.finder._matches = [filematch]
        self.finder.scanned = True

    def __exit__(self, exc_type, exc_val, exc_tb) -> Literal[False]:  # noqa: ANN001
        if self.clear:
            assert len(self.finder._matches) == 0
            assert not self.finder.scanned
        else:
            assert len(self.finder._matches) > 0
            assert self.finder.scanned

        if exc_val is not None:
            raise exc_val
        return False


class TestClearCache:
    def get_finder(self) -> Finder:
        return Finder("", pattern.pattern)

    def assert_cleared(self, finder: Finder, *, clear: bool = True) -> AssertClear:
        return AssertClear(finder, clear)

    def test_nothing(self) -> None:
        finder = self.get_finder()
        with self.assert_cleared(finder, clear=False):
            pass

        with pytest.raises(AssertionError), self.assert_cleared(finder):
            pass

    def test_set_attributes(self) -> None:
        finder = self.get_finder()

        with self.assert_cleared(finder, clear=False):
            finder.set_scan_everything(False)
        with self.assert_cleared(finder, clear=False):
            finder.set_use_regex(False)
        with self.assert_cleared(finder, clear=False):
            finder.set_follow_symlinks(False)

        with self.assert_cleared(finder):
            finder.set_scan_everything(True)
        with self.assert_cleared(finder):
            finder.set_use_regex(True)
        with self.assert_cleared(finder):
            finder.set_follow_symlinks(True)

    def test_set_pattern(self) -> None:
        finder = self.get_finder()

        with self.assert_cleared(finder):
            finder.set_pattern("")

    def test_fix(self) -> None:
        finder = self.get_finder()
        with self.assert_cleared(finder):
            finder.fix(fmt_int=1)

    def test_unfix(self) -> None:
        finder = self.get_finder()

        finder.fix(fmt_int=1, fmt_str="a")
        with self.assert_cleared(finder):
            finder.unfix("fmt_int")

        finder.fix(fmt_int=1)
        with self.assert_cleared(finder):
            finder.unfix()

    def test_filter(self) -> None:
        finder = self.get_finder()

        with self.assert_cleared(finder, clear=False):
            finder.add_filter(lambda *_: True)
        with self.assert_cleared(finder, clear=False):
            finder.add_group_filter("fmt_int", lambda _: True)

        with self.assert_cleared(finder):
            finder.remove_group_filters("fmt_int")
        with self.assert_cleared(finder):
            finder.clear_filters()


class TestFixing:
    def test_fix(self) -> None:
        finder = Finder("", pattern.pattern)
        groups = {g.name: g for g in finder.groups}

        # Fix a single group
        finder.fix(fmt_int=2)
        assert_fixed(groups["fmt_int"], 2, "02", "02")
        for group in finder.groups:
            if group.name != "fmt_int":
                assert_unfixed(group)

        # Fix another single group
        finder.fix(optional=0.5)
        assert_fixed(groups["optional"], 0.5, "_0.5", r"_0\.5")
        for group in finder.groups:
            if group.name not in ["fmt_int", "optional"]:
                assert_unfixed(group)

        # Fix two groups
        finder.fix(fmt_str="a.", bool=True)
        assert_fixed(groups["fmt_str"], "a.", "a.", "a.")
        assert_fixed(groups["bool"], True, "true.", r"true\.")
        for group in finder.groups:
            if group.name not in ["fmt_int", "optional", "fmt_str", "bool"]:
                assert_unfixed(group)

        # Unfix one group
        finder.unfix("bool")
        for group in finder.groups:
            if group.name not in ["fmt_int", "optional", "fmt_str"]:
                assert_unfixed(group)
            else:
                assert group.fixed

        # Unfix two groups
        finder.unfix("fmt_int", "fmt_str")
        for group in finder.groups:
            if group.name not in ["optional"]:
                assert_unfixed(group)
            else:
                assert group.fixed

        # Unfix everything
        finder.unfix()
        for group in finder.groups:
            assert_unfixed(group)

    def test_fix_escape(self) -> None:
        """Test strings are correctly escaped (or not) when fixed.

        Also test fixing of group with prefix.
        """
        finder = Finder("", pattern.pattern)
        groups = {grp.name: grp for grp in finder.groups}

        # Format with a number
        finder.fix(optional=0.5)
        assert_fixed(groups["optional"], 0.5, "_0.5", r"_0\.5")
        finder.unfix()

        # Format with a string
        finder.fix(optional="not+escaped")
        assert_fixed(groups["optional"], "not+escaped", "not+escaped", "not+escaped")

        # Bool with a bool
        finder.fix(bool=False)
        assert_fixed(groups["bool"], False, "false.", r"false\.")

        # Bool with a string
        finder.fix(bool="not+escaped")
        assert_fixed(groups["bool"], "not+escaped", "not+escaped", "not+escaped")

        # Custom regex
        finder.fix(custom_rgx="not+escaped")
        assert_fixed(groups["custom_rgx"], "not+escaped", "not+escaped", "not+escaped")

    def test_fix_double(self) -> None:
        """Test correct fix when multiple groups have the same name."""
        finder = Finder("", pattern_double.pattern)

        finder.fix(fmt_int=1)
        assert_fixed(finder.groups[0], 1, "01", "01")
        assert_fixed(finder.groups[1], 1, "01", "01")

        # Fix by index
        finder.fix({0: 2})
        assert_fixed(finder.groups[0], 2, "02", "02")
        assert_fixed(finder.groups[1], 1, "01", "01")

        # Unfix by index
        finder.unfix(1)
        assert_fixed(finder.groups[0], 2, "02", "02")
        assert_unfixed(finder.groups[1])

    def test_fix_multiple(self) -> None:
        """Test fixing list of values."""
        finder = Finder("", pattern.pattern)
        groups = {grp.name: grp for grp in finder.groups}

        # Format int
        finder.fix(fmt_int=[0, 1, 2])
        assert_fixed(groups["fmt_int"], [0, 1, 2], ["00", "01", "02"], "00|01|02")

        # Format float with prefix
        finder.fix(optional=[0.0, 0.5, 1.0])
        assert_fixed(
            groups["optional"],
            [0.0, 0.5, 1.0],
            ["_0.0", "_0.5", "_1.0"],
            r"_0\.0|_0\.5|_1\.0",
        )

        # Fix two groups
        finder.fix(fmt_str=["a.", "b."], bool=[True, False])
        assert_fixed(groups["fmt_str"], ["a.", "b."], ["a.", "b."], "a.|b.")
        assert_fixed(
            groups["bool"], [True, False], ["true.", "false."], r"true\.|false\."
        )

    def test_fix_date(self) -> None:
        finder = Finder("", pattern_dates.pattern)

        date = dt.datetime(2086, 3, 2)

        finder.fix(date=date)
        assert_fixed(finder.groups[0], 2086, "2086", "2086")
        assert_fixed(finder.groups[1], 2086, "2086", "2086")
        assert_fixed(finder.groups[2], 3, "03", "03")
        assert_fixed(finder.groups[3], 2, "02", "02")
        assert_fixed(finder.groups[4], 61, "061", "061")

        for group in finder.groups[5:]:
            assert_unfixed(group)

        finder.fix(date2=dt.date(2087, 4, 3))
        for i, v in enumerate([2086, 2086, 3, 2, 61]):
            assert finder.groups[i].fixed_value == v

        assert_fixed(finder.groups[5], 2087, "2087", "2087")
        assert_fixed(finder.groups[6], 4, "04", "04")
        assert_fixed(finder.groups[7], 3, "03", "03")
        assert_fixed(finder.groups[8], 93, "093", "093")

    def test_fix_date_wrong(self) -> None:
        finder = Finder("", "%(Y).ext")
        with pytest.raises(TypeError):
            finder.fix(date=1)
        with pytest.raises(TypeError):
            finder.fix(date="2010/05/12")
        with pytest.raises(TypeError):
            finder.fix(date=[dt.datetime(2012, 6, 1), 1])

    def test_fix_date_exotic(self) -> None:
        """Test more complex date elements (F, x, B)."""
        finder = Finder("", "%(date1__F)_%(date2__x)_%(date3__B)")
        assert finder.get_regex() == r"(\d{4}-\d\d-\d\d)_(\d{8})_(\w+)"
        groups = {grp.name: grp for grp in finder.groups}

        finder.fix(date1=dt.date(2086, 1, 2))
        assert_fixed(groups["date1__F"], "2086-01-02", "2086-01-02", r"2086\-01\-02")

        finder.fix(date2=dt.date(2087, 2, 3))
        assert_fixed(groups["date2__x"], 20870203, "20870203", "20870203")

        finder.fix(date3=dt.date(2088, 3, 4))
        assert_fixed(groups["date3__B"], "March", "March", "March")

    def test_fix_multiple_dates(self) -> None:
        def assert_fixed_(groups: dict[str, Group], values: dict) -> None:
            for name, value in values.items():
                assert_fixed(groups[name], value)

        def assert_unfixed_(groups: dict[str, Group], *names: str) -> None:
            for name in names:
                assert_unfixed(groups[name])

        finder = Finder("", "%(Y)%(m)%(d)_%(a__Y)%(a__m)%(a__d)_%(b__Y)%(b__m)%(b__d)")
        groups = {grp.name: grp for grp in finder.groups}

        finder.fix(date=dt.date(2000, 1, 2))
        assert_fixed_(groups, {"Y": 2000, "m": 1, "d": 2})
        assert_unfixed_(groups, "a__Y", "a__m", "a__d", "b__Y", "b__m", "b__d")

        finder.fix(a=dt.date(2010, 3, 4))
        assert_fixed_(groups, {"Y": 2000, "m": 1, "d": 2})
        assert_fixed_(groups, {"a__Y": 2010, "a__m": 3, "a__d": 4})
        assert_unfixed_(groups, "b__Y", "b__m", "b__d")

        finder.unfix("date")
        assert_unfixed_(groups, "Y", "m", "d")
        assert_fixed_(groups, {"a__Y": 2010, "a__m": 3, "a__d": 4})

        finder.fix(b=dt.date(2020, 5, 6), date=dt.date(2030, 7, 8))
        assert_fixed_(groups, {"Y": 2030, "m": 7, "d": 8})
        assert_fixed_(groups, {"a__Y": 2010, "a__m": 3, "a__d": 4})
        assert_fixed_(groups, {"b__Y": 2020, "b__m": 5, "b__d": 6})


class TestMatches:
    def get_filematch(self, filename: str | None = None) -> tuple[Finder, FileMatch]:
        if filename is None:
            filename = "A_05_abc_def_true._-15.2.txt"

        finder = Finder("", pattern.pattern)
        filematch = finder.find_matches(filename)

        assert filematch is not None
        assert len(filematch) == len(finder.groups)

        return finder, filematch

    def test_unparsed(self) -> None:
        """Test accessing unparsed matches."""
        _, filematch = self.get_filematch()

        assert filematch.get_value("fmt_int", parse=False) == "05"
        assert filematch.get_value("fmt_str", parse=False) == "abc"
        assert filematch.get_value("custom_rgx", parse=False) == "def"
        assert filematch.get_value("bool", parse=False) == "true."
        assert filematch.get_value("optional", parse=False) == "_-15.2"

        # Make sure we have not triggered any parsing
        for group_match in filematch.matches:
            assert group_match._parsed is ParseStatus.NOT_PARSED

    def test_parse(self) -> None:
        """Test parsing values."""
        _, filematch = self.get_filematch()

        assert filematch.get_value("fmt_int") == 5
        assert filematch.get_value("fmt_str") == "abc"
        assert filematch.get_value("custom_rgx") == "def"
        assert filematch.get_value("bool") is True
        assert filematch.get_value("optional") == -15.2

        assert filematch["fmt_int"] == 5
        assert filematch["fmt_str"] == "abc"
        assert filematch["custom_rgx"] == "def"
        assert filematch["bool"] is True
        assert filematch["optional"] == -15.2

        # Make sure the parsed value is cached
        for group_match in filematch.matches:
            assert group_match._parsed is not ParseStatus.NOT_PARSED

    def test_optional(self) -> None:
        """Test optional group has empty match."""
        _, filematch = self.get_filematch("A_05_abc_def_true..txt")
        assert filematch is not None

        assert filematch.get_value("optional", parse=False) == ""
        assert filematch["optional"] is None

    def test_bad_parse(self) -> None:
        """Test status value is set, and raises when necessary."""
        finder = Finder("", "%(a:fmt=d:rgx=.*)")
        filematch = finder.find_matches("bad")
        assert filematch is not None

        assert filematch.get_value("a", parse=False) == "bad"
        with pytest.raises(ValueError):
            assert filematch.get_value("a")

        assert filematch.matches[0]._parsed is ParseStatus.FAILED
        assert filematch.matches[0].get_match(raise_on_unparsed=False) == "bad"

    def test_multiple_values(self) -> None:
        """Test parsing with multiple groups of the same name."""
        finder = Finder("", pattern_double.pattern)
        filematch = finder.find_matches("A-01_B-01_C-a.txt")
        assert filematch is not None
        assert filematch.get_values("fmt_int") == [1, 1]
        assert filematch["fmt_int"] == 1

        filematch = finder.find_matches("A-01_B-02_C-a.txt")
        assert filematch is not None
        assert filematch.get_values("fmt_int") == [1, 2]
        # first value is selected
        with pytest.warns(UserWarning):
            assert filematch["fmt_int"] == 1

    def test_date(self) -> None:
        """Test retrieving dates."""
        finder = Finder("", pattern_dates.pattern)
        filematch = finder.find_matches(
            os.path.join("2086", "20860302-061_20870403-093.txt")
        )
        assert filematch is not None

        assert filematch["Y"] == 2086
        assert filematch["m"] == 3
        assert filematch["date2__Y"] == 2087
        assert filematch["date2__j"] == 93

        assert filematch["date"] == dt.datetime(2086, 3, 2)
        assert filematch["date2"] == dt.datetime(2087, 4, 3)

    @pytest.mark.parametrize("pattern", pattern_examples)
    def test_wrong_filename(self, pattern: PatternExample) -> None:
        """Test obviously wrong filenames that won't match."""
        f = Finder("", pattern.pattern)
        assert f.find_matches("bawhatever") is None


class TestMakeFilename:
    def test_by_value(self) -> None:
        finder = Finder("base", pattern.pattern)

        fixes: dict[str, Any] = {
            "fmt_int": 1,
            "fmt_str": "a+",
            "custom_rgx": "b+",
            "bool": True,
            "optional": 0.1,
        }
        filename = os.path.join("base", "A_01_a+_b+_true._0.1.txt")

        assert finder.make_filename(fixes) == filename
        assert finder.make_filename(**fixes) == filename

        finder.fix(fixes)
        assert finder.make_filename() == filename

    def test_by_str(self) -> None:
        """String values are not escaped."""
        finder = Finder("base", pattern.pattern)

        fixes: dict[str, Any] = {
            "fmt_int": "a+",
            "fmt_str": "b+",
            "custom_rgx": "c+",
            "bool": "d+",
            "optional": "e+",
        }
        filename = os.path.join("base", "A_a+_b+_c+_d+e+.txt")

        assert finder.make_filename(fixes) == filename
        assert finder.make_filename(**fixes) == filename

        finder.fix(fixes)
        assert finder.make_filename() == filename

    def test_wrong(self) -> None:
        finder = Finder("base", pattern.pattern)

        with pytest.raises(KeyError):
            finder.make_filename()
        with pytest.raises(KeyError):
            finder.make_filename(fmt_int=1, bool=True)

        finder = Finder("", "", use_regex=True)
        with pytest.raises(ValueError):
            finder.make_filename()

    def test_fixed(self) -> None:
        """Test that only some values can be fixed, and correct overwrite."""
        finder = Finder("base", pattern.pattern)

        finder.fix(
            fmt_int=1,
            fmt_str="a+",
            bool=True,
        )
        assert finder.make_filename(custom_rgx="b+", optional=0.5) == os.path.join(
            "base", "A_01_a+_b+_true._0.5.txt"
        )

        assert finder.make_filename(
            custom_rgx="b+", optional=0.5, fmt_int=5
        ) == os.path.join("base", "A_05_a+_b+_true._0.5.txt")

    def test_optional(self) -> None:
        """Optional groups do not have to be fixed."""
        finder = Finder("base", pattern.pattern)

        finder.fix(
            fmt_int=1,
            fmt_str="a+",
            bool=True,
        )
        assert finder.make_filename(
            fmt_int=1, fmt_str="a", custom_rgx="b", bool=False
        ) == os.path.join("base", "A_01_a_b_false..txt")

    def test_multiple_fix(self) -> None:
        """The first value is used when fixed to multiple values."""
        finder = Finder("base", pattern.pattern)

        finder.fix(
            fmt_int=[1, 2, 3],
            fmt_str=["a1", "a2"],
            bool=[True, False],
        )
        assert finder.make_filename(
            custom_rgx=["b1", "b2"], optional=[0.5, 0.6, 0.7]
        ) == os.path.join("base", "A_01_a1_b1_true._0.5.txt")

        assert finder.make_filename(
            custom_rgx=["b1"], optional=[0.5, 0.6, 0.7], fmt_int=[2, 3]
        ) == os.path.join("base", "A_02_a1_b1_true._0.5.txt")

    def test_doubles(self) -> None:
        """Multiple groups with the same name are correctly handled."""
        finder = Finder("base", pattern_double.pattern)
        assert finder.make_filename(fmt_int=1, other=True) == os.path.join(
            "base", "A-01_B-01_C-a.txt"
        )

        finder.fix(fmt_int=1)
        assert finder.make_filename({0: 2}, other=True) == os.path.join(
            "base", "A-02_B-01_C-a.txt"
        )

    def test_dates(self) -> None:
        finder = Finder("base", pattern_dates.pattern)

        assert finder.make_filename(
            date=dt.datetime(2086, 3, 2), date2=dt.datetime(2087, 4, 3)
        ) == os.path.join("base", "2086", "20860302-061_20870403-093.txt")

        finder.fix(date=dt.datetime(2086, 3, 2), date2=dt.datetime(2087, 4, 3))
        assert finder.make_filename({"date2__d": 4}, d=3) == os.path.join(
            "base", "2086", "20860303-061_20870404-093.txt"
        )


class TestFileScan:
    def setup(self, tmp_path: Path) -> None:
        self.tmp_dir = TmpDirectoryExample(tmp_path)
        for i in range(20):
            self.tmp_dir.create_file(f"invalid_files_{i}.ext", save=False)
        self.finder = self.tmp_dir.get_filefinder()

    def assert_files(self, ref_files: Sequence[str]) -> None:
        assert len(self.finder.matches) == len(ref_files)
        for f, f_ref in zip(
            self.finder.get_files(relative=True), ref_files, strict=False
        ):
            assert f == f_ref

    def test_setup(self, tmp_path: Path) -> None:
        tmp_dir = TmpDirectoryExample(
            tmp_path, dates=[dt.datetime(2086, 2, 3)], params=[0.0], options=[1, None]
        )
        finder = tmp_dir.get_filefinder()

        files = [
            os.path.join("2086", "test_2086-02-03_0.0.txt"),
            os.path.join("2086", "test_2086-02-03_0.0_01.txt"),
        ]
        assert tmp_dir.files == files
        assert finder.get_files(relative=True) == files

    def test_simple(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.assert_files(self.tmp_dir.files)

    def test_fix_parameter(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.fix(param=0)
        self.assert_files(self.tmp_dir.make_filenames(params=[0]))

    def test_fix_date(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        year = 2001
        self.finder.fix(Y=year)
        fixed_dates = [d for d in self.tmp_dir.dates if d.year == year]
        self.assert_files(self.tmp_dir.make_filenames(dates=fixed_dates))

    def test_fix_option(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.fix(option=None)
        self.assert_files(self.tmp_dir.make_filenames(options=[None]))
        self.finder.fix(option=[1, 2])
        self.assert_files(self.tmp_dir.make_filenames(options=[1, 2]))
        self.finder.fix(option=[None, 1, 2])
        self.assert_files(self.tmp_dir.make_filenames(options=[None, 1, 2]))

    def test_filter_parameter(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.add_group_filter("param", lambda x: abs(x) > 0)  # type: ignore[arg-type]
        self.assert_files(self.tmp_dir.make_filenames(params=[-1.5, 1.5]))

    def test_fix_and_filter_parameter(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.fix(param=[0, 1.5])
        self.finder.add_group_filter("param", lambda x: abs(x) > 0)  # type: ignore[arg-type]
        self.assert_files(self.tmp_dir.make_filenames(params=[1.5]))

    def test_filter_date(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.add_group_filter(
            "date",
            lambda d: dt.datetime(2000, 6, 1) <= d <= dt.datetime(2001, 6, 1),  # type: ignore[arg-type]
        )
        fixed_dates = date_range((2000, 6, 14), 15, 24)
        self.assert_files(self.tmp_dir.make_filenames(dates=fixed_dates))

    def test_fix_and_filter_date(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.fix(Y=2000)
        self.finder.add_group_filter(
            "date",
            lambda d: dt.datetime(2000, 6, 1) <= d <= dt.datetime(2001, 6, 1),  # type: ignore[arg-type]
        )
        fixed_dates = date_range((2000, 6, 14), 15, 14)
        self.assert_files(self.tmp_dir.make_filenames(dates=fixed_dates))

    def test_filter_option(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.add_group_filter("option", lambda x: x is not None and x > 1)
        self.assert_files(self.tmp_dir.make_filenames(options=[2]))
        self.finder.clear_filters()
        self.finder.add_group_filter("option", lambda x: x is None or x > 1)
        self.assert_files(self.tmp_dir.make_filenames(options=[None, 2]))

    def test_manual_filter(self, tmp_path: Path) -> None:
        self.setup(tmp_path)
        self.finder.fix(param=0)
        self.assert_files(self.tmp_dir.make_filenames(params=[0]))

    def test_opt_directory(self, tmp_path: Path) -> None:
        """Test having a directory separator in an optional group."""
        tmp_dir = TmpDirectory(tmp_path)

        files = [
            "0.txt",
            f"a{os.sep}1.txt",
            f"b{os.sep}2.txt",
            f"a{os.sep}c{os.sep}3.txt",
            f"b{os.sep}d{os.sep}4.txt",
        ]
        files.sort()
        for f in files:
            tmp_dir.create_file(f)

        finder = Finder(
            str(tmp_dir.base_dir),
            "%(folder:rgx=[a-z]/:opt)%(folder:rgx=[a-z]/:opt)%(param:fmt=d).txt",
            scan_everything=True,
        )
        assert len(finder.get_files()) == len(files)
        for f, f_ref in zip(finder.get_files(relative=True), files, strict=False):
            assert f == f_ref

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="Changing permission does not work on Windows (easily)",
    )
    def test_permission_warning(self, tmp_path: Path) -> None:
        tmp_dir = TmpDirectory(tmp_path)
        tmp_dir.create_dir("inacessible")
        tmp_dir.create_file("inacessible/a.txt")

        (tmp_dir.base_dir / "inacessible").chmod(0)

        finder = Finder(str(tmp_dir.base_dir), "inacessible/%(a:rgx=a).txt")
        with pytest.warns(UserWarning):
            finder.find_files()

    def test_follow_symlink(self, tmp_path: Path) -> None:
        tmp_dir = TmpDirectory(tmp_path)
        files = []
        for f in [
            ("a0", "a00", "a00.file"),
            ("a0", "a01", "a01.file"),
            ("a1", "a10", "a10.file"),
            ("a1", "a11", "a11.file"),
        ]:
            files.append(tmp_dir.create_file(os.path.join(*f)))

        # Finder base dir will be "a1", will not find two first files
        files = files[2:]

        os.symlink(tmp_dir.base_dir / "a1" / "a10", tmp_dir.base_dir / "a1" / "a12")
        files.append(str(tmp_dir.base_dir / "a1" / "a12" / "a10.file"))

        # follow_symlinks = False
        finder = Finder(
            str(tmp_dir.base_dir / "a1"),
            r"%(l1:rgx=a\d\d)/%(l2:rgx=a\d\d).file",
        )
        assert files[:2] == finder.get_files()

        finder = Finder(
            str(tmp_dir.base_dir / "a1"),
            r"%(l1:rgx=a\d\d)/%(l2:rgx=a\d\d).file",
            follow_symlinks=True,
        )
        assert sorted(files) == finder.get_files()

        # Add symlink going outside of base dir
        os.symlink(tmp_dir.base_dir / "a0" / "a00", tmp_dir.base_dir / "a1" / "a03")
        files.append(str(tmp_dir.base_dir / "a1" / "a03" / "a00.file"))

        # Add a misdirect (the different depth should not allow matching)
        os.symlink(tmp_dir.base_dir / "a0", tmp_dir.base_dir / "a1" / "a04")
        finder = Finder(
            str(tmp_dir.base_dir / "a1"),
            r"%(l1:rgx=a\d\d)/%(l2:rgx=a\d\d).file",
            follow_symlinks=True,
        )
        assert sorted(files) == finder.get_files()


class TestFileScanNested:
    """Test simple case of nested filenames output."""

    tmp_dir: TmpDirectoryExample
    finder: Finder

    def setup_test(self, tmp_path: Path) -> tuple[list, list, list]:
        self.tmp_dir = TmpDirectoryExample(tmp_path, create=True)

        for i in range(20):
            self.tmp_dir.create_file(f"invalid_files_{i}.ext", save=False)

        self.finder = self.tmp_dir.get_filefinder()
        assert len(self.finder.matches) == len(self.tmp_dir.files)
        self.finder.clear_cache()

        return self.tmp_dir.dates, self.tmp_dir.params, self.tmp_dir.options

    def test_nest_by_param(self, tmp_path: Path) -> None:
        dates, params, options = self.setup_test(tmp_path)

        nested_param = self.finder.get_files(relative=True, nested=["param"])
        assert len(nested_param) == len(params)

        for param_ref, nested_inner in zip(params, nested_param, strict=False):
            nest_ref_files = self.tmp_dir.make_filenames(dates, [param_ref], options)
            assert len(nested_inner) == len(nest_ref_files)
            for f, f_ref in zip(nested_inner, nest_ref_files, strict=False):
                assert f == f_ref

    def test_nest_by_year(self, tmp_path: Path) -> None:
        dates, params, options = self.setup_test(tmp_path)

        nested_y = self.finder.get_files(relative=True, nested=["Y"])
        years = sorted({d.year for d in dates})
        assert len(nested_y) == len(years)

        for year_ref, nested_inner in zip(years, nested_y, strict=False):
            nested_inner_ref = self.tmp_dir.make_filenames(
                [d for d in dates if d.year == year_ref],
                params,
                options,
            )
            assert len(nested_inner) == len(nested_inner_ref)
            for f, f_ref in zip(nested_inner, nested_inner_ref, strict=False):
                assert f == f_ref

    def test_nest_by_option_param(self, tmp_path: Path) -> None:
        dates, params, options = self.setup_test(tmp_path)

        nested_option = self.finder.get_files(relative=True, nested=["option", "param"])
        assert len(nested_option) == len(options)

        for option_ref, nested_param in zip(options, nested_option, strict=False):
            assert len(nested_param) == len(params)
            for param_ref, nested_inner in zip(params, nested_param, strict=False):
                assert len(nested_inner) == len(dates)
                nested_inner_ref = self.tmp_dir.make_filenames(
                    dates, [param_ref], [option_ref]
                )
                for f, f_ref in zip(nested_inner, nested_inner_ref, strict=False):
                    assert f == f_ref

    def test_nest_by_everything(self, tmp_path: Path) -> None:
        dates, params, options = self.setup_test(tmp_path)

        nested_param = self.finder.get_files(
            relative=True, nested=["param", "option", "Y", "m", "d"]
        )
        assert len(nested_param) == len(params)
        for param_ref, nested_option in zip(params, nested_param, strict=False):
            assert len(nested_option) == len(options)
            for option_ref, nested_y in zip(options, nested_option, strict=False):
                years = sorted({d.year for d in dates})
                assert len(nested_y) == len(years)
                for y_ref, nested_m in zip(years, nested_y, strict=False):
                    dates_y = [d for d in dates if d.year == y_ref]
                    months = sorted({d.month for d in dates_y})
                    assert len(nested_m) == len(months)
                    for m_ref, nested_d in zip(months, nested_m, strict=False):
                        dates_m = [d for d in dates_y if d.month == m_ref]
                        days = sorted({d.day for d in dates_m})
                        assert len(nested_d) == len(dates_m)
                        for d_ref, nested_inner in zip(days, nested_d, strict=False):
                            assert len(nested_inner) == 1
                            filename = self.tmp_dir.make_filename(
                                dt.datetime(y_ref, m_ref, d_ref), param_ref, option_ref
                            )
                            assert nested_inner[0] == filename
