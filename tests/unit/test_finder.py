"""Test main features."""

import itertools
import os
from datetime import datetime, timedelta
from os import path

from filefinder import Finder


def assert_pattern(pattern, regex):
    finder = Finder("", pattern)
    assert finder.get_regex() == regex


def test_date_groups():
    assert_pattern("test_%(x).ext", r"test_(\d{4}\d\d\d\d)\.ext")
    assert_pattern("test_%(Y).ext", r"test_(\d{4})\.ext")
    assert_pattern("test_%(Y)-%(m)-%(d).ext", r"test_(\d{4})\-(\d\d)\-(\d\d)\.ext")


def test_multiple_groups():
    finder = Finder("", "test_%(m)_%(d)")
    assert finder.n_groups == 2
    assert finder.groups[0].name == "m"
    assert finder.groups[1].name == "d"


def test_custom_regex():
    assert_pattern("test_%(Y:rgx=[a-z]*?)", "test_([a-z]*?)")
    assert_pattern("test_%(Y:fmt=d:rgx=[a-z]*?)", "test_([a-z]*?)")


def test_format_regex():
    assert_pattern("test_%(Y:fmt=d)", r"test_(-?\d+)")
    assert_pattern("test_%(Y:fmt=a>5d)", r"test_(a*-?\d+)")
    assert_pattern("test_%(Y:fmt=a<5d)", r"test_(-?\d+a*)")
    assert_pattern("test_%(Y:fmt=a^5d)", r"test_(a*-?\d+a*)")
    assert_pattern("test_%(Y:fmt=05.3f)", r"test_(-?0*\d+\.\d{3})")
    assert_pattern("test_%(Y:fmt=+05.3f)", r"test_([+-]0*\d+\.\d{3})")
    assert_pattern("test_%(Y:fmt=.2e)", r"test_(-?\d\.\d{2}e[+-]\d+)")
    assert_pattern("test_%(Y:fmt=.2E)", r"test_(-?\d\.\d{2}E[+-]\d+)")


def test_name_group():
    def assert_group_name(pattern, names):
        finder = Finder("", pattern)
        for m, name in zip(finder.groups, names):
            assert m.name == name

    assert_group_name("test_%(foo:fmt=.2f)", ["foo"])
    assert_group_name("test_%(foo:fmt=d)_%(bar:fmt=s)", ["foo", "bar"])


def test_optional():
    assert_pattern("test_%(m:opt)", r"test_(\d\d)?")


def test_boolean():
    assert_pattern("test_%(bar:bool=A:B)", "test_(A|B)")
    assert_pattern("test_%(bar:bool=A:)", "test_(A|)")
    assert_pattern("test_%(bar:bool=A)", "test_(A|)")


def test_fix_group_string():
    finder = Finder("", "test_%(m)_%(c:fmt=.1f)")
    finder.fix_group(0, "01")
    finder.fix_group(1, r"11\.1")
    assert finder.get_regex() == r"test_(01)_(11\.1)"


def test_fix_group_value():
    finder = Finder("", "test_%(m)_%(c:fmt=.1f)_%(b:bool=A:B)")
    finder.fix_group(0, 1)
    finder.fix_group(1, 11)
    finder.fix_group(2, True)
    assert finder.get_regex() == r"test_(01)_(11\.0)_(A)"


def test_get_groups():
    def assert_get_groups(finder, key, indices):
        assert indices == [g.idx for g in finder.get_groups(key)]

    finder = Finder("", "test_%(m)_%(c:fmt=.1f)_%(d)_%(d)")
    assert_get_groups(finder, "m", [0])
    assert_get_groups(finder, "c", [1])
    assert_get_groups(finder, "d", [2, 3])


def test_make_filename():
    root = path.join("data", "root")
    filename_rel = "test_01_5.00_yes"
    filename_abs = path.join(root, filename_rel)
    finder = Finder(root, "test_%(m)_%(c:fmt=.2f)_%(b:bool=yes)")

    # Without fix
    assert finder.make_filename(m=1, c=5, b=True) == filename_abs
    # With dictionnary
    assert finder.make_filename(dict(m=1, c=5, b=True)) == filename_abs
    # With mix
    assert finder.make_filename(dict(m=1, c=5), b=True) == filename_abs
    # Relative file
    assert finder.make_filename(relative=True, m=1, c=5, b=True) == filename_rel

    # With fix
    finder.fix_groups(m=1)
    assert finder.make_filename(c=5, b=True) == filename_abs
    assert finder.make_filename(dict(c=5), b=True) == filename_abs


dates = [datetime(2000, 1, 1) + i * timedelta(days=15) for i in range(50)]
params = [-1.5, 0.0, 1.5]
options = [False, True]


# TODO add files than do not match
# TODO test nested
# TODO test if create finder, change use_regex, and use it


def test_file_scan(fs):
    datadir = path.sep + "data"
    fs.create_dir(datadir)
    files = []
    for d, p, o in itertools.product(dates, params, options):
        filename = "{}{}test_{}_{:.1f}{}.ext".format(
            d.year, path.sep, d.strftime("%F"), p, "_yes" if o else ""
        )
        files.append(filename)
        fs.create_file(path.join(datadir, filename))
    files.sort()

    finder = Finder(
        datadir,
        (
            f"%(Y){path.sep}test_%(Y)-%(m)-%(d)_"
            "%(param:fmt=.1f)%(option:bool=_yes).ext"
        ),
    )
    assert len(finder.files) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref


def test_opt_directory(fs):
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
        f"%(folder:rgx=[a-z]{path.sep}:opt)"
        f"%(folder:rgx=[a-z]{path.sep}:opt)"
        "%(param:fmt=d).txt",
        scan_everything=True,
    )
    assert len(finder.get_files()) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref
