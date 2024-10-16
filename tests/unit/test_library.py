"""Test library functions.

Presentely, only `library.get_date`.
"""

import itertools
import os
from collections import abc
from datetime import datetime, timedelta
from os import path

import filefinder.library
import pyfakefs
from filefinder.finder import Finder
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from util import FORBIDDEN_CHAR, MAX_CODEPOINT, MAX_TEXT_SIZE, setup_files

group_names: list[str] = list("FxXYmdBjHMS")
"""List of group names that are understood as date by filefinder."""

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
            st.sampled_from(group_names),
            min_size=1,
            max_size=len(group_names),
            unique=True,
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
    segments[::2] = [draw(text) for _ in range(len(names) + 1)]

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
    # start from the default date
    default_elements = {
        attr: getattr(default_date, attr)
        for attr in ["year", "month", "day", "hour", "minute", "second"]
    }
    elements = dict(default_elements)
    # fill in elements present in pattern
    names = segments[1::2]
    for name in group_names:
        if name not in names:
            continue
        for elt in name_to_date[name]:
            elements[elt] = getattr(date, elt)

    try:
        date_ref = datetime(**elements)
    except ValueError:
        # from combining elements and default date, we might have a day value that
        # is too high for the month
        return

    # format ourselves, datetime.strftime does not always zero pad for some reason
    for i, name in enumerate(names):
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

    for i, name in enumerate(names):
        segments[2 * i + 1] = f"%({name})"
    pattern = "".join(segments)

    finder = Finder("", pattern)
    matches = finder.find_matches(filename)
    assert matches is not None
    date_parsed = filefinder.library.get_date(matches, default_elements)

    assert date_ref == date_parsed


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
    assert len(finder.files) == ndays * len(params) * 2

    finder.fix_groups(m=[5, 6])
    finder.clear_filters()
    finder.add_filter(
        filefinder.library.filter_date_range,
        start=datetime(2000, 5, 10),
        stop=datetime(2000, 6, 10),
    )
    assert len(finder.files) == ndays * len(params) * 2

    finder.fix_groups(m=2)
    assert len(finder.files) == 0


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

    # test adding filter without re-scanning files
    finder.add_filter(filefinder.library.filter_by_range, group="param", max=10)
    nvalues = 10 - 5 + 1
    assert len(finder.files) == 2 * len(dates) * nvalues

    finder.clear_filters()
    finder.add_filter(filefinder.library.filter_by_range, group="param", min=10, max=15)
    nvalues = 15 - 10 + 1
    assert len(finder.files) == 2 * len(dates) * nvalues
