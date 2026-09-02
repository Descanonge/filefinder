"""Test date related functions."""

import calendar
import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from filefinder.dates import (
    _find_month_number,
    date_from_doy,
    datetime_to_str,
    datetime_to_value,
    get_doy,
    make_date_groups,
)


def test_make_date_groups() -> None:
    assert make_date_groups("%Y%m%d%j%F") == "%(Y)%(m)%(d)%(j)%(F)"
    assert make_date_groups("%Y%m%d%j%F", name="a") == "%(a:Y)%(a:m)%(a:d)%(a:j)%(a:F)"


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
