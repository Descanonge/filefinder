"""Test library functions.

Presentely, only `library.get_date`.
"""

import os
from datetime import datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from util import FORBIDDEN_CHAR, MAX_CODEPOINT, MAX_TEXT_SIZE, setup_files

import filefinder.library
from filefinder.finder import Finder
from filefinder.util import datetime_keys

name_to_date = {
    "F": ["year", "month", "day"],
    "x": ["year", "month", "day"],
    "X": ["hour", "minute", "second"],
    "Y": ["year"],
    "m": ["month"],
    "B": ["month"],
    "d": ["day"],
    "j": ["month", "day"],
    "H": ["hour"],
    "M": ["minute"],
    "S": ["second"],
}
"""Elements of datetime to set for each group."""


@st.composite
def segments(draw) -> list[str]:
    """Generate pattern segments with date elements."""
    names = draw(
        st.lists(
            st.sampled_from(datetime_keys),
            min_size=1,
            max_size=len(datetime_keys),
        )
    )

    text = st.text(
        alphabet=st.characters(
            max_codepoint=MAX_CODEPOINT,
            exclude_categories=["C"],
            exclude_characters=set("%()\\") | FORBIDDEN_CHAR,
        ),
        min_size=0,
        max_size=MAX_TEXT_SIZE,
    )

    segments = ["" for _ in range(2 * len(names) + 1)]
    segments[1::2] = names
    for i in range(len(names) + 1):
        strat = text
        # force at least one char after written month name, otherwise parsing
        # is impossible
        if names[i - 1] == "B":
            strat = strat.filter(lambda s: len(s) > 0)
        segments[2 * i] = draw(strat)

    return segments


@settings(suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None)
@given(segments=segments(), date=st.datetimes(), default_date=st.datetimes())
def test_get_date(segments: list[str], date: datetime, default_date: datetime):
    """Test obtaining a date from a pattern.

    Parameters
    ----------
    segments
        Segments indicating the pattern. Odd elements are group names, even elements
        text. The pattern and a filename are generated from it.
    date
        Date to generate a filename with and to test parsing.
    default_date
        Random default date for `library.get_date`.
    """
    ELEMENTS = ["year", "month", "day", "hour", "minute", "second"]
    # Construct a reference date that will mix appropriately with the default_date
    # based on what elements are present in the pattern
    default_elements = {attr: getattr(default_date, attr) for attr in ELEMENTS}
    elements = dict(default_elements)

    group_names = segments[1::2]
    elements_specified = set()
    for name in group_names:
        for elt in name_to_date[name]:
            elements[elt] = getattr(date, elt)
            elements_specified.add(elt)

    try:
        date_ref = datetime(**elements)
    except ValueError:
        # from combining elements and default date, we might have a day value that
        # is too high for the month
        return

    # format ourselves, datetime.strftime does not always zero pad for some reason
    for i, name in enumerate(group_names):
        if name == "F":
            seg = f"{date_ref.year:04d}-{date_ref.month:02d}-{date_ref.day:02d}"
        elif name == "x":
            seg = f"{date_ref.year:04d}{date_ref.month:02d}{date_ref.day:02d}"
        elif name == "X":
            seg = date_ref.strftime("%H%M%S")
        elif name == "Y":
            seg = f"{date_ref.year:04d}"
        else:
            seg = date_ref.strftime(f"%{name}")
        segments[2 * i + 1] = seg

    filename = "".join(segments).replace("/", os.sep)

    for i, name in enumerate(group_names):
        segments[2 * i + 1] = f"%({name})"
    pattern = "".join(segments)

    finder = Finder("", pattern)
    matches = finder.find_matches(filename)
    assert matches is not None
    date_parsed = filefinder.library.get_date(matches, default_elements)

    for elt in elements_specified:
        assert getattr(date_ref, elt) == getattr(date_parsed, elt)
    for elt in set(ELEMENTS) - elements_specified:
        assert getattr(default_date, elt) == getattr(date_parsed, elt)


def test_invalid_file_differing_elements():
    finder = Finder("", "%(Y)/%(m)/%(F).ext")
    filenames = ["2005/01/2006-01-02.ext", "2005/01/2005-03-01.ext"]
    for f in filenames:
        with pytest.raises(ValueError):
            filefinder.library.get_date(finder.find_matches(f))


def test_no_date_matchers(caplog):
    finder = Finder("", "%(year:fmt=02d)/%(month:fmt=02d)/%(full:fmt=s).ext")
    filenames = ["2005/01/2006-01-02.ext", "2005/01/2005-03-01.ext"]
    for f in filenames:
        filefinder.library.get_date(finder.find_matches(f))
        warnings = any(
            rec.levelname == "WARNING"
            and rec.msg.startswith("No date elements could be recovered.")
            for rec in caplog.records
        )
        assert warnings


def assert_nfiles(finder, n_files: int):
    assert len(finder.files) == n_files
    finder._void_cache()
    assert len(finder.files) == n_files


def test_filter_dates(fs):
    dates = [datetime(2000, 1, 1) + i * timedelta(days=1) for i in range(365)]
    params = list(range(20))
    datadir, files = setup_files(fs, dates, params)

    finder = Finder(
        datadir,
        "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
    )

    # Simple case
    finder.add_filter(
        filefinder.library.filter_date_range, start="2000-01-01", stop="2000-01-02"
    )
    ndays = 2
    assert len(finder.files) == ndays * len(params) * 2

    finder.clear_filters()
    finder.add_filter(
        filefinder.library.filter_date_range, start="2000-05-10", stop="2000-06-10"
    )
    ndays = 32
    assert_nfiles(finder, ndays * 2 * len(params))

    finder.fix_groups(m=[5, 6])
    finder.clear_filters()
    finder.add_filter(
        filefinder.library.filter_date_range,
        start=datetime(2000, 5, 10),
        stop=datetime(2000, 6, 10),
    )
    assert_nfiles(finder, ndays * 2 * len(params))

    finder.fix_groups(m=2)
    assert_nfiles(finder, 0)


def test_fix_by_filter_dates(fs):
    dates = [datetime(2000, 1, 1) + i * timedelta(days=1) for i in range(365)]
    params = list(range(20))
    datadir, files = setup_files(fs, dates, params)

    finder = Finder(
        datadir,
        "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
    )

    # Simple case
    finder.fix_by_filter(
        "date", lambda d: datetime(2000, 1, 1) <= d <= datetime(2000, 1, 2)
    )
    ndays = 2
    assert_nfiles(finder, ndays * len(params) * 2)

    finder.clear_filters()
    finder.fix_by_filter(
        "date", lambda d: datetime(2000, 5, 10) <= d <= datetime(2000, 6, 10)
    )
    ndays = 32
    assert_nfiles(finder, ndays * len(params) * 2)
    assert len(finder.files) == ndays * len(params) * 2

    finder.fix_groups(m=[5, 6])
    finder.clear_filters()
    finder.fix_by_filter(
        "date", lambda d: datetime(2000, 5, 10) <= d <= datetime(2000, 6, 10)
    )
    assert_nfiles(finder, ndays * len(params) * 2)

    finder.fix_groups(m=2)
    assert_nfiles(finder, 0)

    finder.clear_filters()
    finder.unfix_groups()
    finder.fix_by_filter("date", lambda d: d.month % 2 == 0)
    ndays = 181
    assert_nfiles(finder, ndays * len(params) * 2)


def test_filter_values(fs):
    dates = [datetime(2000, 1, 1) + i * timedelta(days=1) for i in range(60)]
    params = list(range(20))
    datadir, files = setup_files(fs, dates, params)

    finder = Finder(
        datadir,
        "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
    )

    finder.add_filter(filefinder.library.filter_by_range, group="param", min=5)
    nvalues = 19 - 5 + 1
    assert len(finder.files) == 2 * len(dates) * nvalues

    finder.add_filter(filefinder.library.filter_by_range, group="param", max=10)
    nvalues = 10 - 5 + 1
    assert_nfiles(finder, 2 * len(dates) * nvalues)

    finder.clear_filters()
    finder.add_filter(filefinder.library.filter_by_range, group="param", min=10, max=15)
    nvalues = 15 - 10 + 1
    assert_nfiles(finder, 2 * len(dates) * nvalues)


def test_filter_group(fs):
    dates = [datetime(2000, 1, 1) + i * timedelta(days=1) for i in range(60)]
    params = list(range(20))
    datadir, files = setup_files(fs, dates, params)

    finder = Finder(
        datadir,
        "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
    )

    finder.fix_by_filter("m", lambda m: m == 1)
    assert len(finder.files) == 2 * 31 * len(params)

    finder.fix_by_filter("option", bool)
    assert_nfiles(finder, 31 * len(params))

    # test unfixing
    finder.unfix_groups("m")
    assert_nfiles(finder, len(dates) * len(params))

    finder.fix_by_filter("param", lambda x: x < 10)
    assert_nfiles(finder, len(dates) * 10)

    finder.fix_by_filter("param", lambda x: x % 2 == 0)
    assert_nfiles(finder, len(dates) * 5)
