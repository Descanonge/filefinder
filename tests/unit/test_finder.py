"""Test main features."""

import itertools
import logging
import os
from datetime import datetime, timedelta
from os import path

import pytest
from filefinder import Finder
from hypothesis import HealthCheck, given, settings
from hypothesis.strategies._internal.misc import JustStrategy
from pyfakefs.fake_filesystem import FakeFilesystem
from util import StPattern, StructPattern

log = logging.getLogger(__name__)


def assert_pattern(pattern, regex):
    finder = Finder("", pattern)
    assert finder.get_regex() == regex


@given(struct=StPattern.pattern(separate=False))
def test_group_names(struct: StructPattern):
    f = Finder("", struct.pattern)
    assert f.n_groups == len(f.groups) == len(struct.groups)

    for i in range(f.n_groups):
        assert f.groups[i].name == struct.groups[i].name


@given(struct=StPattern.pattern(separate=False))
def test_get_groups(struct: StructPattern):
    f = Finder("", struct.pattern)

    names = set(g.name for g in struct.groups)

    for name in names:
        indices_ref = [i for i, g in enumerate(struct.groups) if g.name == name]
        indices = [g.idx for g in f.get_groups(name)]
        assert indices_ref == indices


@given(struct=StPattern.pattern_with_values())
def test_match_filename_values(struct: StructPattern):
    """Test values in a matched filename are correctly parsed.

    Pattern is generated automatically with appropriate values (and formatted values).
    The reference filename is constructed from the pattern segments and the formatted
    values that were drawn.

    For each group that has a definition allowing to generate a value, we check that
    filefinder has correctly parsed the value back.
    If the group has no discard flag, we also test Matches.__getitem__.
    """
    # reference filename
    filename = struct.filename

    f = Finder("", struct.pattern)
    matches = f.find_matches(filename)

    # Correct number of matches
    assert len(matches) == len(struct.groups)

    for i, (val, val_str) in enumerate(zip(struct.values, struct.values_str)):
        # Unparsable group definition
        if val is not None:
            assert matches.get_value(key=i, parse=True, discard=False) == val
            if not struct.groups[i].discard:
                assert matches[i] == val
            else:
                with pytest.raises(KeyError):
                    _ = matches[i]

        assert matches.get_value(key=i, parse=False, discard=False) == val_str


@given(struct=StPattern.pattern_with_values())
def test_make_filename(struct: StructPattern):
    """Test filename creation."""
    f = Finder("/base/", struct.pattern)
    fixes = {i: s for i, s in enumerate(struct.values_str)}
    assert f.make_filename(fixes, relative=True) == struct.filename


@pytest.mark.parametrize("pattern", ["ab%(foo:fmt=d)", "ab%(foo:rgx=.*)"])
def test_wrong_filename(pattern: str):
    """Test obviously wrong filenames that won't match.

    Not sure if there is a way to generate wrong filenames in the most general case.
    """
    f = Finder("", pattern)
    with pytest.raises(ValueError):
        f.find_matches("bawhatever")


# Tested systematically in test_group.test_random_definitions
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


# It is possible to add random files, but it is difficult to ensure they will not
# match... It is easy to find counter examples.
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    struct=StPattern.pattern_with_multiple_values()
    .filter(lambda p: all(not isinstance(g, JustStrategy) for g in p.groups))
    .filter(lambda p: not p.pattern.endswith("/")),
)
def test_file_scan(fs: FakeFilesystem, struct: StructPattern):
    data_dirname = "data"
    basedir = fs.root_dir_name + data_dirname
    try:
        fs.root_dir.remove_entry(data_dirname)
    except KeyError:
        pass
    fs.create_dir(basedir)

    files = list(struct.filenames)
    files = list(set(files))
    files.sort()
    for f in files:
        fs.create_file(basedir + fs.path_separator + f)

    log.info("pattern: %s", struct.pattern)
    log.info("n_files: %d", len(files))
    finder = Finder(basedir, struct.pattern)
    assert len(finder.files) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref


# TODO test nested
# TODO test if create finder, change use_regex, and use it


def test_file_scan_manual(fs):
    dates = [datetime(2000, 1, 1) + i * timedelta(days=15) for i in range(50)]
    params = [-1.5, 0.0, 1.5]
    options = [False, True]

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

    for i in range(20):
        fs.create_file(path.join(datadir, f"invalid_files_{i}.ext"))

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
