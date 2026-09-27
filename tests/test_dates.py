"""Test date related functions."""

import calendar
import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from filefinder.dates import (
    DATETIME_ATTRIBUTES,
    DATETIME_KEYS,
    DateParser,
    _find_month_number,
    date_from_doy,
    datetime_to_str,
    datetime_to_value,
    get_doy,
    make_date_groups,
)
from filefinder.group import Group
from filefinder.matches import GroupMatch


def test_make_date_groups() -> None:
    assert make_date_groups("%Y%m%d%j%F") == "%(Y)%(m)%(d)%(j)%(F)"
    assert (
        make_date_groups("%Y%m%d%j%F", name="a")
        == "%(a__Y)%(a__m)%(a__d)%(a__j)%(a__F)"
    )
    assert make_date_groups("%Y%m%dT%H:%M:%S") == "%(Y)%(m)%(d)T%(H):%(M):%(S)"


def test_datetime_to_str() -> None:
    date = dt.datetime(2086, 3, 2, 1, 34, 6)
    assert datetime_to_str(date, "Y") == "2086"
    assert datetime_to_str(date, "m") == "03"
    assert datetime_to_str(date, "d") == "02"
    assert datetime_to_str(date, "B") == calendar.month_name[3]
    assert datetime_to_str(date, "j") == "061"

    assert datetime_to_str(date, "H") == "01"
    assert datetime_to_str(date, "M") == "34"
    assert datetime_to_str(date, "S") == "06"

    assert datetime_to_str(date, "x") == "20860302"
    assert datetime_to_str(date, "X") == "013406"
    assert datetime_to_str(date, "F") == "2086-03-02"

    with pytest.raises(KeyError):
        datetime_to_str(date, "NOT_A_KEY")
    with pytest.raises(TypeError):
        datetime_to_str(dt.date(2000, 1, 1), "H")


def test_datetime_to_value_basic() -> None:
    date = dt.datetime(2086, 3, 2, 1, 34, 6)
    assert datetime_to_value(date, "Y") == 2086
    assert datetime_to_value(date, "m") == 3
    assert datetime_to_value(date, "d") == 2
    assert datetime_to_value(date, "B") == calendar.month_name[3]
    assert datetime_to_value(date, "j") == 61

    assert datetime_to_value(date, "H") == 1
    assert datetime_to_value(date, "M") == 34
    assert datetime_to_value(date, "S") == 6

    assert datetime_to_value(date, "x") == 20860302
    assert datetime_to_value(date, "X") == 13406
    assert datetime_to_value(date, "F") == "2086-03-02"

    with pytest.raises(KeyError):
        datetime_to_value(date, "NOT_A_KEY")
    with pytest.raises(TypeError):
        datetime_to_value(dt.date(2000, 1, 1), "H")


@given(date=st.datetimes())
def test_datetime_to_value(date: dt.datetime) -> None:
    assert datetime_to_value(date, "Y") == date.year
    assert datetime_to_value(date, "m") == date.month
    assert datetime_to_value(date, "d") == date.day
    assert datetime_to_value(date, "H") == date.hour
    assert datetime_to_value(date, "M") == date.minute
    assert datetime_to_value(date, "S") == date.second

    for name in "FB":
        assert datetime_to_value(date, name) == datetime_to_str(date, name)
    for name in "xX":
        assert datetime_to_value(date, name) == int(datetime_to_str(date, name))


def test_get_doy() -> None:
    assert get_doy(dt.datetime(2004, 1, 1)) == 1
    assert get_doy(dt.datetime(2004, 1, 2)) == 2
    assert get_doy(dt.datetime(2004, 2, 1)) == 32
    assert get_doy(dt.datetime(2004, 3, 1)) == 61
    assert get_doy(dt.datetime(2005, 3, 1)) == 60


def test_date_from_doy() -> None:
    assert date_from_doy(1, 2004) == {"month": 1, "day": 1}
    assert date_from_doy(2, 2004) == {"month": 1, "day": 2}
    assert date_from_doy(32, 2004) == {"month": 2, "day": 1}
    assert date_from_doy(61, 2004) == {"month": 3, "day": 1}
    assert date_from_doy(60, 2005) == {"month": 3, "day": 1}


@given(date=st.datetimes())
def test_date_to_doy_and_back(date: dt.datetime) -> None:
    doy = get_doy(date)
    back = date_from_doy(doy, date.year)
    assert back["month"] == date.month
    assert back["day"] == date.day


@given(doy=st.integers(1, 365), year=st.integers(1, 3000))
def test_doy_to_date_and_back(doy: int, year: int) -> None:
    elts = date_from_doy(doy, year)
    date = dt.datetime(year, elts["month"], elts["day"])
    back = get_doy(date)
    assert doy == back


@given(month=st.integers(1, 12))
def test_find_month_number(month: int) -> None:
    name = calendar.month_name[month]
    assert _find_month_number(name) == month


class TestDateParser:
    @given(year=st.integers(0, 9999))
    def test_process_Y(self, year: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("Y", 0), str(year), 0, 0)
        parser = DateParser([gm])
        assert parser.process_YmdHMS(gm) == {"year": year}

    @given(month=st.integers(0, 12))
    def test_process_m(self, month: int) -> None:
        gm = GroupMatch(Group("m", 0), f"{month:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_YmdHMS(gm) == {"month": month}

    @given(day=st.integers(0, 31))
    def test_process_d(self, day: int) -> None:
        gm = GroupMatch(Group("d", 0), f"{day:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_YmdHMS(gm) == {"day": day}

    @given(hour=st.integers(0, 24))
    def test_process_H(self, hour: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("H", 0), f"{hour:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_YmdHMS(gm) == {"hour": hour}

    @given(minute=st.integers(0, 24))
    def test_process_M(self, minute: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("M", 0), f"{minute:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_YmdHMS(gm) == {"minute": minute}

    @given(second=st.integers(0, 24))
    def test_process_S(self, second: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("S", 0), f"{second:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_YmdHMS(gm) == {"second": second}

    @given(date=st.dates())
    def test_process_F(self, date: dt.date) -> None:  # noqa: N802
        gm = GroupMatch(Group("F", 0), date.strftime("%F"), 0, 0)
        parser = DateParser([gm])
        assert parser.process_F(gm) == {
            "year": date.year,
            "month": date.month,
            "day": date.day,
        }

    @given(date=st.dates())
    def test_process_x(self, date: dt.date) -> None:
        gm = GroupMatch(
            Group("x", 0), f"{date.year}{date.month:02d}{date.day:02d}", 0, 0
        )
        parser = DateParser([gm])
        assert parser.process_x(gm) == {
            "year": date.year,
            "month": date.month,
            "day": date.day,
        }

    @given(time=st.times())
    def test_process_X(self, time: dt.time) -> None:  # noqa: N802
        gm = GroupMatch(
            Group("X", 0), f"{time.hour:02d}{time.minute:02d}{time.second:02d}", 0, 0
        )
        parser = DateParser([gm])
        assert parser.process_X(gm) == {
            "hour": time.hour,
            "minute": time.minute,
            "second": time.second,
        }

    @given(date=st.dates())
    def test_process_j(self, date: dt.date) -> None:
        gm = GroupMatch(Group("j", 0), date.strftime("%j"), 0, 0)
        parser = DateParser([gm], default_date={"year": date.year})
        assert parser.process_j(gm) == {"month": date.month, "day": date.day}

    @given(date=st.datetimes())
    def test_parse(self, date: dt.datetime) -> None:
        """Test parsing a date from all elements."""
        # remove microsecond
        date = date.replace(microsecond=0)
        matches = [
            GroupMatch(Group("Y", 0), date.strftime("%Y"), 0, 0),
            GroupMatch(Group("m", 0), date.strftime("%m"), 0, 0),
            GroupMatch(Group("d", 0), date.strftime("%d"), 0, 0),
            GroupMatch(Group("H", 0), date.strftime("%H"), 0, 0),
            GroupMatch(Group("M", 0), date.strftime("%M"), 0, 0),
            GroupMatch(Group("S", 0), date.strftime("%S"), 0, 0),
            GroupMatch(Group("j", 0), date.strftime("%j"), 0, 0),
            GroupMatch(Group("B", 0), date.strftime("%B"), 0, 0),
            GroupMatch(Group("F", 0), date.strftime("%Y-%m-%d"), 0, 0),
            GroupMatch(Group("x", 0), date.strftime("%Y%m%d"), 0, 0),
            GroupMatch(Group("X", 0), date.strftime("%H%M%S"), 0, 0),
        ]
        assert DateParser.parse(matches) == date

        # alternative way
        parser = DateParser(matches)
        assert parser.retrieve_date() == date

    @given(
        date=st.datetimes(),
        default_date=st.datetimes(),
        elements=st.lists(st.sampled_from(DATETIME_KEYS), min_size=1),
    )
    def test_parse_with_default(
        self, date: dt.datetime, default_date: dt.datetime, elements: list[str]
    ) -> None:
        date_ref_elements = {
            attr: getattr(default_date, attr)
            for attr in ["year", "month", "day", "hour", "minute", "second"]
        }
        for element in elements:
            for attr in DATETIME_ATTRIBUTES[element]:
                date_ref_elements[attr] = getattr(date, attr)
        date_ref = dt.datetime(**date_ref_elements)

        matches = [
            GroupMatch(Group(element, 0), datetime_to_str(date_ref, element), 0, 0)
            for element in elements
        ]

        assert DateParser.parse(matches, default_date=default_date) == date_ref
