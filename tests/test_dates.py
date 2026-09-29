"""Test date related functions."""

import calendar
import datetime as dt

import pytest
from hypothesis import given
from hypothesis import strategies as st

from filefinder.dates import (
    DATETIME_ELEMENTS,
    DateParser,
    _datetime_to_dict,
    _find_month_number,
    datetime_to_str,
    datetime_to_value,
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
    assert datetime_to_str(date, "T") == "013406"
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


@given(month=st.integers(1, 12))
def test_find_month_number(month: int) -> None:
    name = calendar.month_name[month]
    assert _find_month_number(name) == month


class TestDateParser:
    @given(month=st.integers(1, 12))
    def test_process_B(self, month: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("B", 0), dt.date(1970, month, 1).strftime("%B"), 0, 0)
        parser = DateParser([gm])
        assert parser.process_B() == {"month": month}

    @given(month=st.integers(1, 12))
    def test_process_b(self, month: int) -> None:
        gm = GroupMatch(Group("b", 0), dt.date(1970, month, 1).strftime("%b"), 0, 0)
        parser = DateParser([gm])
        assert parser.process_b() == {"month": month}

    @given(day=st.integers(0, 31))
    def test_process_d(self, day: int) -> None:
        gm = GroupMatch(Group("d", 0), f"{day:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"day": day}

    @given(microsecond=st.integers(0, 1000000))
    def test_process_f(self, microsecond: int) -> None:
        gm = GroupMatch(Group("f", 0), f"{microsecond:06d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"microsecond": microsecond}

    @given(date=st.dates())
    def test_process_F(self, date: dt.date) -> None:  # noqa: N802
        gm = GroupMatch(Group("F", 0), date.strftime("%F"), 0, 0)
        parser = DateParser([gm])
        assert parser.process_F() == {
            "year": date.year,
            "month": date.month,
            "day": date.day,
        }

    @given(hour=st.integers(0, 24))
    def test_process_H(self, hour: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("H", 0), f"{hour:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"hour": hour}

    @given(date=st.dates())
    def test_process_j(self, date: dt.date) -> None:
        # Year from other group
        gm = GroupMatch(Group("j", 0), date.strftime("%j"), 0, 0)
        gm_year = GroupMatch(Group("Y", 0), str(date.year), 0, 0)
        parser = DateParser([gm_year, gm])
        parser.process("Y", parser.process_basic)
        assert parser.process_j() == {"month": date.month, "day": date.day}

        # Year from default date
        parser = DateParser([gm], default_date={"year": date.year})
        assert parser.process_j() == {"month": date.month, "day": date.day}

    @given(month=st.integers(0, 12))
    def test_process_m(self, month: int) -> None:
        gm = GroupMatch(Group("m", 0), f"{month:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"month": month}

    @given(minute=st.integers(0, 24))
    def test_process_M(self, minute: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("M", 0), f"{minute:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"minute": minute}

    @given(second=st.integers(0, 24))
    def test_process_S(self, second: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("S", 0), f"{second:02d}", 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"second": second}

    @given(
        date=st.datetimes(),
        offset_hr=st.integers(0, 23),
        offset_min=st.integers(0, 59),
        neg=st.booleans(),
    )
    def test_process_s(
        self, date: dt.datetime, offset_hr: int, offset_min: int, neg: bool
    ) -> None:
        delta = dt.timedelta(hours=offset_hr, minutes=offset_min)
        if neg:
            delta = -delta
        tz_ref = dt.timezone(delta)
        tz_str = f"{'-' if neg else ''}{offset_hr:02d}{offset_min:02d}"

        date = date.replace(microsecond=0)  # , tzinfo=tz_ref)

        matches = [
            GroupMatch(Group("z", 0), tz_str, 0, 0),
            GroupMatch(Group("s", 0), date.strftime("%s"), 0, 0),
        ]
        parser = DateParser(matches)
        # parser.process("z", parser.process_z)
        assert parser.process_s() == {
            "year": date.year,
            "month": date.month,
            "day": date.day,
            "hour": date.hour,
            "minute": date.minute,
            "second": date.second,
            "microsecond": date.microsecond,
        }

    @given(time=st.times())
    def test_process_T(self, time: dt.time) -> None:  # noqa: N802
        gm = GroupMatch(
            Group("T", 0), f"{time.hour:02d}{time.minute:02d}{time.second:02d}", 0, 0
        )
        parser = DateParser([gm])
        assert parser.process_T() == {
            "hour": time.hour,
            "minute": time.minute,
            "second": time.second,
        }

    @given(date=st.dates())
    def test_process_x(self, date: dt.date) -> None:
        gm = GroupMatch(
            Group("x", 0), f"{date.year}{date.month:02d}{date.day:02d}", 0, 0
        )
        parser = DateParser([gm])
        assert parser.process_x() == {
            "year": date.year,
            "month": date.month,
            "day": date.day,
        }

    @given(year=st.integers(0, 9999))
    def test_process_Y(self, year: int) -> None:  # noqa: N802
        gm = GroupMatch(Group("Y", 0), str(year), 0, 0)
        parser = DateParser([gm])
        assert parser.process_basic() == {"year": year}

    @given(tz=st.timezones())
    def test_process_z(self, tz: dt.timezone) -> None:
        date = dt.datetime(2000, 1, 1, tzinfo=tz)
        gm = GroupMatch(Group("z", 0), date.strftime("%z"), 0, 0)
        parser = DateParser([gm])

        # Need this to convert from zoneinfo.ZoneInfo to datetime.timezone
        tz_delta = tz.utcoffset(date)
        if tz_delta is None:
            tz_delta = dt.timedelta()
        assert parser.process_z() == {"tzinfo": dt.timezone(tz_delta)}

    @given(hour=st.integers(0, 23))
    def test_process_hour_12(self, hour: int) -> None:
        time = dt.time(hour=hour)
        matches = [
            GroupMatch(Group("I", 0), time.strftime("%I"), 0, 0),
            GroupMatch(Group("p", 0), time.strftime("%p"), 0, 0),
        ]
        parser = DateParser(matches)
        assert parser.process_hour_12() == {"hour": hour}

        with pytest.raises(ValueError):
            DateParser(matches[:1]).process_hour_12()
        with pytest.raises(ValueError):
            DateParser(matches[1:]).process_hour_12()

    @given(
        date=st.dates(),
        weekday_fmt=st.sampled_from("aAuw"),
        weeknumber_fmt=st.sampled_from("UW"),
    )
    def test_process_week_day(
        self, date: dt.date, weekday_fmt: str, weeknumber_fmt: str
    ) -> None:
        matches = [
            GroupMatch(Group("Y", 0), date.strftime("%Y"), 0, 0),
            GroupMatch(Group(weekday_fmt, 0), date.strftime(f"%{weekday_fmt}"), 0, 0),
            GroupMatch(
                Group(weeknumber_fmt, 0), date.strftime(f"%{weeknumber_fmt}"), 0, 0
            ),
        ]
        parser = DateParser(matches)
        parser.process("Y", parser.process_basic)
        assert parser.process_week_day() == {"month": date.month, "day": date.day}

    @given(date=st.datetimes(timezones=st.timezones()))
    def test_parse(self, date: dt.datetime) -> None:
        """Test parsing a date from all elements."""
        # remove microsecond
        date = date.replace(microsecond=0)
        # group_fmt = {x: f"%{x}" for x in DATETIME_ELEMENTS}
        group_fmt = {x: f"%{x}" for x in "FT"}
        group_fmt["F"] = "%Y-%m-%d"
        group_fmt["x"] = "%Y%m%d"
        group_fmt["T"] = "%H%M%S"
        matches = [
            GroupMatch(Group(name, 0), datetime_to_str(date, name), 0, 0)
            for name in DATETIME_ELEMENTS
        ]
        assert DateParser.parse(matches) == date

        # alternative way
        parser = DateParser(matches)
        assert parser.retrieve_date() == date

    @given(
        date=st.datetimes(timezones=st.one_of([st.none(), st.timezones()])),
        default_date=st.datetimes(timezones=st.one_of([st.none(), st.timezones()])),
        elements=st.lists(st.sampled_from(DATETIME_ELEMENTS), min_size=1),
    )
    def test_parse_with_default(
        self, date: dt.datetime, default_date: dt.datetime, elements: list[str]
    ) -> None:

        elements_attributes = {
            "a": ["month", "day"],
            "A": ["month", "day"],
            "b": ["month"],
            "B": ["month"],
            "d": ["day"],
            "f": ["microsecond"],
            "F": ["year", "month", "day"],
            "H": ["hour"],
            "I": ["hour"],
            "j": ["month", "day"],
            "m": ["month"],
            "M": ["minute"],
            "p": [],
            "P": [],
            "s": ["year", "month", "day", "hour", "minute", "second"],
            "S": ["second"],
            "T": ["hour", "minute", "second"],
            "u": ["month", "day"],
            "U": ["month", "day"],
            "w": ["month", "day"],
            "W": ["month", "day"],
            "Y": ["year"],
            "z": ["tzinfo"],
        }

        if "z" in elements:
            date = date.replace(tzinfo=dt.UTC)

        date_ref_elements = _datetime_to_dict(default_date)

        for element in elements:
            for attr in elements_attributes[element]:
                date_ref_elements[attr] = getattr(date, attr)
        date_ref = dt.datetime(**date_ref_elements)

        matches = [
            GroupMatch(Group(element, 0), datetime_to_str(date_ref, element), 0, 0)
            for element in elements
        ]

        has_ampm = len(set("pP") & set(elements)) > 0
        has_hour12 = "I" in elements
        has_weekday = len(set("aAuw") & set(elements)) > 0
        has_weeknum = len((set("UW")) & set(elements)) > 0

        if has_ampm != has_hour12:
            with pytest.raises(ValueError):
                DateParser.parse(matches)
            return
        if has_weekday != has_weeknum:
            with pytest.raises(ValueError):
                DateParser.parse(matches)
            return

        parser = DateParser(matches, default_date=default_date)
        parsed = parser.retrieve_date()
        assert parsed == date_ref
