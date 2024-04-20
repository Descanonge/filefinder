"""Test library functions.

Presentely, only `library.get_date`.
"""

import os
import typing as t
from datetime import datetime

import filefinder.library
from filefinder.finder import Finder
from hypothesis import assume, given
from hypothesis import strategies as st
from util import FORBIDDEN_CHAR, MAX_CODEPOINT, MAX_TEXT_SIZE

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


@given(
    segments=segments(),
    date=st.datetimes(),
    default_date=st.datetimes(),
)
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
