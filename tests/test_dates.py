"""Test date related functions."""

import calendar
import datetime as dt
import platform
from zoneinfo import ZoneInfo

import pytest
from hypothesis import given
from hypothesis import strategies as st
from lib import Drawer

from filefinder.dates import (
    DATETIME_ELEMENTS,
    STRING_ELEMENTS,
    TIME_ELEMENTS,
    DateParser,
    datetime_to_str,
    datetime_to_value,
    make_date_groups,
)
from filefinder.group import Group
from filefinder.matches import GroupMatch


def st_tzinfo() -> st.SearchStrategy[dt.timezone]:
    @st.composite
    def strat(draw: Drawer) -> dt.timezone:
        neg = draw(st.booleans())

        args = {
            "hours": draw(st.integers(0, 23)),
            "minutes": draw(st.integers(0, 59)),
            "seconds": draw(st.one_of(st.none(), st.integers(0, 59))),
            "microseconds": draw(st.one_of(st.none(), st.integers(0, 999999))),
        }
        args = {k: v for k, v in args.items() if v is not None}
        delta = dt.timedelta(**args)  # type: ignore[arg-type]
        if neg:
            delta = -delta

        return dt.timezone(delta)

    return strat()


def fix_year_windows(date: dt.datetime) -> dt.datetime:
    """Windows does not support timestamps outside of 1970-2038."""
    if platform.system() == "Windows":
        year, month, day = date.year, date.month, date.day
        year = min(max(year, 1970), 2038)
        day = min(day, calendar.monthrange(year, month)[1])
        date = date.replace(year=year, day=day)

    return date


def test_make_date_groups() -> None:
    assert make_date_groups("%Y%m%d%j%F") == "%(Y)%(m)%(d)%(j)%(F)"
    assert (
        make_date_groups("%Y%m%d%j%F", name="a")
        == "%(a__Y)%(a__m)%(a__d)%(a__j)%(a__F)"
    )
    assert make_date_groups("%Y%m%dT%H:%M:%S") == "%(Y)%(m)%(d)T%(H):%(M):%(S)"


class TestDatetimeToStr:
    def test_manual(self) -> None:
        date = dt.datetime(2026, 2, 3, 14, 34, 6, 654, tzinfo=ZoneInfo("Etc/GMT+1"))
        assert datetime_to_str(date, "a") == calendar.day_abbr[1]
        assert datetime_to_str(date, "A") == calendar.day_name[1]
        assert datetime_to_str(date, "b") == calendar.month_abbr[2]
        assert datetime_to_str(date, "B") == calendar.month_name[2]
        assert datetime_to_str(date, "d") == "03"
        assert datetime_to_str(date, "f") == "000654"
        assert datetime_to_str(date, "F") == "2026-02-03"
        assert datetime_to_str(date, "H") == "14"
        assert datetime_to_str(date, "I") == "02"
        assert datetime_to_str(date, "j") == "034"
        assert datetime_to_str(date, "m") == "02"
        assert datetime_to_str(date, "M") == "34"
        assert datetime_to_str(date, "p") == "PM"
        assert datetime_to_str(date, "P") == "pm"
        assert datetime_to_str(date, "s") == "1770132846.000654"
        assert datetime_to_str(date, "S") == "06"
        assert datetime_to_str(date, "T") == "143406"
        assert datetime_to_str(date, "u") == "2"
        assert datetime_to_str(date, "U") == "05"
        assert datetime_to_str(date, "w") == "2"
        assert datetime_to_str(date, "W") == "05"
        assert datetime_to_str(date, "x") == "20260203"
        assert datetime_to_str(date, "Y") == "2026"
        assert datetime_to_str(date, "z") == "-0100"

        with pytest.raises(KeyError):
            datetime_to_str(date, "NOT_A_KEY")
        for name in TIME_ELEMENTS:
            with pytest.raises(TypeError):
                datetime_to_str(dt.date(2000, 1, 1), name)

    def test_naive(self) -> None:
        date = dt.datetime(2026, 2, 3, 14, 34, 6)
        assert datetime_to_str(date, "F") == "2026-02-03"
        assert datetime_to_str(date, "H") == "14"
        assert datetime_to_str(date, "I") == "02"
        assert datetime_to_str(date, "p") == "PM"
        assert datetime_to_str(date, "P") == "pm"
        assert datetime_to_str(date, "s") == "1770129246.000000"
        assert datetime_to_str(date, "T") == "143406"
        assert datetime_to_str(date, "z") == "+0000"


class TestDatetimeToValue:
    def test_manual(self) -> None:
        date = dt.datetime(2026, 2, 3, 14, 34, 6, 654, tzinfo=ZoneInfo("Etc/GMT+1"))
        assert datetime_to_value(date, "a") == calendar.day_abbr[1]
        assert datetime_to_value(date, "A") == calendar.day_name[1]
        assert datetime_to_value(date, "b") == calendar.month_abbr[2]
        assert datetime_to_value(date, "B") == calendar.month_name[2]
        assert datetime_to_value(date, "d") == 3
        assert datetime_to_value(date, "f") == 654
        assert datetime_to_value(date, "F") == "2026-02-03"
        assert datetime_to_value(date, "H") == 14
        assert datetime_to_value(date, "I") == 2
        assert datetime_to_value(date, "j") == 34
        assert datetime_to_value(date, "m") == 2
        assert datetime_to_value(date, "M") == 34
        assert datetime_to_value(date, "p") == "PM"
        assert datetime_to_value(date, "P") == "pm"
        assert datetime_to_value(date, "s") == 1770132846.000654
        assert datetime_to_value(date, "S") == 6
        assert datetime_to_value(date, "T") == "143406"
        assert datetime_to_value(date, "u") == 2
        assert datetime_to_value(date, "U") == 5
        assert datetime_to_value(date, "w") == 2
        assert datetime_to_value(date, "W") == 5
        assert datetime_to_value(date, "x") == "20260203"
        assert datetime_to_value(date, "Y") == 2026
        assert datetime_to_value(date, "z") == "-0100"

        with pytest.raises(KeyError):
            datetime_to_str(date, "NOT_A_KEY")
        for name in TIME_ELEMENTS:
            with pytest.raises(TypeError):
                datetime_to_str(dt.date(2000, 1, 1), name)

    @given(date=st.datetimes(timezones=st.timezones()))
    def test_hypothesis(self, date: dt.datetime) -> None:
        assert datetime_to_value(date, "Y") == date.year
        assert datetime_to_value(date, "m") == date.month
        assert datetime_to_value(date, "d") == date.day
        assert datetime_to_value(date, "j") == int(date.strftime("%j"))

        assert datetime_to_value(date, "H") == date.hour
        assert datetime_to_value(date, "M") == date.minute
        assert datetime_to_value(date, "S") == date.second
        assert datetime_to_value(date, "f") == date.microsecond
        assert datetime_to_value(date, "s") == date.timestamp()

        assert datetime_to_value(date, "u") == date.weekday() + 1
        assert datetime_to_value(date, "U") == int(date.strftime("%U"))
        assert datetime_to_value(date, "w") == int(date.strftime("%w"))
        assert datetime_to_value(date, "W") == int(date.strftime("%W"))

        for element in STRING_ELEMENTS:
            assert datetime_to_value(date, element) == datetime_to_str(date, element)

    def test_naive(self) -> None:
        date = dt.datetime(2026, 2, 3, 14, 34, 6)
        assert datetime_to_value(date, "d") == 3
        assert datetime_to_value(date, "F") == "2026-02-03"
        assert datetime_to_value(date, "H") == 14
        assert datetime_to_value(date, "I") == 2
        assert datetime_to_value(date, "j") == 34
        assert datetime_to_value(date, "m") == 2
        assert datetime_to_value(date, "M") == 34
        assert datetime_to_value(date, "p") == "PM"
        assert datetime_to_value(date, "P") == "pm"
        assert datetime_to_value(date, "s") == 1770129246.000000
        assert datetime_to_value(date, "S") == 6
        assert datetime_to_value(date, "T") == "143406"
        assert datetime_to_value(date, "z") == "+0000"

        with pytest.raises(KeyError):
            datetime_to_str(date, "NOT_A_KEY")
        for name in TIME_ELEMENTS:
            with pytest.raises(TypeError):
                datetime_to_str(dt.date(2000, 1, 1), name)


class TestDateParser:
    @given(date=st.dates())
    def test_prepare_F(self, date: dt.date) -> None:  # noqa: N802
        s = datetime_to_str(date, "F")
        gm = GroupMatch(Group("F", 0), s, 0, 0)
        parser = DateParser([gm])

        elements = {
            "Y": f"{date.year:04d}",
            "m": f"{date.month:02d}",
            "d": f"{date.day:02d}",
        }

        assert parser.prepare_F(s) == elements
        assert parser.elements == elements

    @given(date=st.dates())
    def test_process_x(self, date: dt.date) -> None:
        s = datetime_to_str(date, "x")
        gm = GroupMatch(Group("x", 0), s, 0, 0)
        parser = DateParser([gm])

        elements = {
            "Y": f"{date.year:04d}",
            "m": f"{date.month:02d}",
            "d": f"{date.day:02d}",
        }

        assert parser.prepare_x(s) == elements
        assert parser.elements == elements

    @given(time=st.times())
    def test_process_T(self, time: dt.time) -> None:  # noqa: N802
        s = f"{time.hour:02d}{time.minute:02d}{time.second:02d}"
        gm = GroupMatch(Group("T", 0), s, 0, 0)
        parser = DateParser([gm])

        elements = {
            "H": f"{time.hour:02d}",
            "M": f"{time.minute:02d}",
            "S": f"{time.second:02d}",
        }

        assert parser.prepare_T(s) == elements
        assert parser.elements == elements

    @given(s=st.sampled_from(["am", "pm"]))
    def test_process_P(self, s: str) -> None:  # noqa: N802
        gm = GroupMatch(Group("P", 0), s, 0, 0)
        parser = DateParser([gm])

        elements = {"p": s.upper()}

        assert parser.prepare_P(s) == elements
        assert parser.elements == elements

    @given(tz=st.timezones())
    def test_parse_z(self, tz: dt.timezone) -> None:
        date = dt.datetime(2000, 1, 1, tzinfo=tz)
        tz_str = datetime_to_str(date, "z")

        # Need this to convert from zoneinfo.ZoneInfo to datetime.timezone
        tz_delta = tz.utcoffset(date)
        if tz_delta is None:
            tz_delta = dt.timedelta()

        parser = DateParser([])
        assert parser.parse_z(tz_str) == dt.timezone(tz_delta)

    @given(tz=st_tzinfo())
    def test_process_z_elements(self, tz: dt.timezone) -> None:
        tz_str = datetime_to_str(dt.datetime(2000, 1, 1, tzinfo=tz), "z")
        parser = DateParser([])

        assert parser.parse_z(tz_str) == tz

    @given(
        date=st.datetimes(
            min_value=dt.datetime(1800, 1, 1), max_value=dt.datetime(2200, 1, 1)
        ),
        tz=st.one_of(st.none(), st_tzinfo()),
    )
    def test_process_s(self, date: dt.datetime, tz: dt.timezone | None) -> None:
        date = date.replace(tzinfo=tz)
        date = fix_year_windows(date)

        ts_str = datetime_to_str(date, "s")
        parser = DateParser([])

        assert parser.parse_s(ts_str, tz) == date

    @given(date=st.datetimes(), tzinfo=st.one_of(st.timezones(), st_tzinfo()))
    def test_parse_simple(self, date: dt.datetime, tzinfo: dt.timezone) -> None:
        """Test parsing a date from all elements."""
        # convert to timedelta based, otherwise comparison will fail
        tzdelta = tzinfo.utcoffset(date)

        date = fix_year_windows(date)

        if not 1800 < date.year < 2200:
            # timestamp breaks at the microsecond level
            date = date.replace(microsecond=0)
            tzdelta -= dt.timedelta(microseconds=tzdelta.microseconds)

        date = date.replace(tzinfo=dt.timezone(tzdelta))

        matches = [
            GroupMatch(Group(name, 0), datetime_to_str(date, name), 0, 0)
            for name in "YmdHMSfz"
        ]
        assert DateParser(matches).parse() == date

    @given(
        date=st.dates(),
        weekday_elt=st.sampled_from("aAuw"),
        weeknum_elt=st.sampled_from("UW"),
    )
    def test_parse_weekdaynumber(
        self, date: dt.date, weekday_elt: str, weeknum_elt: str
    ) -> None:
        gm_year = GroupMatch(Group("Y", 0), datetime_to_str(date, "Y"), 0, 0)
        gm_weekday = GroupMatch(
            Group(weekday_elt, 0), datetime_to_str(date, weekday_elt), 0, 0
        )
        gm_weeknum = GroupMatch(
            Group(weeknum_elt, 0), datetime_to_str(date, weeknum_elt), 0, 0
        )

        # Full
        assert DateParser([gm_year, gm_weekday, gm_weeknum]).parse().date() == date

        # Missing one
        with pytest.raises(ValueError):
            DateParser([gm_year, gm_weekday]).parse()
        with pytest.raises(ValueError):
            DateParser([gm_year, gm_weeknum]).parse()

        # Missing one - with default
        parser = DateParser(
            [gm_year, gm_weekday],
            default_date={weeknum_elt: datetime_to_value(date, weeknum_elt)},
        )
        assert parser.parse().date() == date

        parser = DateParser(
            [gm_year, gm_weeknum],
            default_date={weekday_elt: datetime_to_value(date, weekday_elt)},
        )
        assert parser.parse().date() == date

        # Missing one - other match is used
        matches = [
            gm_year,
            GroupMatch(Group(weeknum_elt, 0), "42", 0, 0),  # should be ignored
            GroupMatch(Group("j", 0), datetime_to_str(date, "j"), 0, 0),
        ]
        parser = DateParser(matches)
        assert parser.parse().date() == date

    @given(hour=st.integers(0, 23))
    def test_parse_hour12(self, hour: int) -> None:
        date = dt.datetime(1970, 1, 1, hour, 0, 0)
        gm_hour = GroupMatch(Group("I", 0), datetime_to_str(date, "I"), 0, 0)
        gm_ampm = GroupMatch(Group("p", 0), datetime_to_str(date, "p"), 0, 0)

        # Full
        assert DateParser([gm_hour, gm_ampm]).parse() == date

        # Missing one
        with pytest.raises(ValueError):
            DateParser([gm_hour]).parse()
        with pytest.raises(ValueError):
            DateParser([gm_ampm]).parse()

        # Missing one - with default
        parser = DateParser(
            [gm_hour],
            default_date={"p": datetime_to_value(date, "p")},
        )
        assert parser.parse() == date

        # Missing one - other match is used
        matches = [
            GroupMatch(Group("I", 0), "05", 0, 0),  # should be ignored
            GroupMatch(Group("H", 0), datetime_to_str(date, "H"), 0, 0),
        ]
        parser = DateParser(matches)
        assert parser.parse() == date

    @given(
        date=st.datetimes(
            min_value=dt.datetime(1800, 1, 1),
            max_value=dt.datetime(2200, 1, 1),
            timezones=st.one_of(st.timezones(), st_tzinfo()),
        ),
        default_date=st.datetimes(timezones=st.one_of(st.none(), st_tzinfo())),
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
            "s": ["year", "month", "day", "hour", "minute", "second", "microsecond"],
            "S": ["second"],
            "T": ["hour", "minute", "second"],
            "u": ["month", "day"],
            "U": ["month", "day"],
            "w": ["month", "day"],
            "W": ["month", "day"],
            "x": ["year", "month", "day"],
            "Y": ["year"],
            "z": ["tzinfo"],
        }

        has_ampm = len(set("pP") & set(elements)) > 0
        has_hour12 = "I" in elements
        has_weekday = len(set("aAuw") & set(elements)) > 0
        has_weeknum = len(set("UW") & set(elements)) > 0
        has_month = len(set("bBmjFxs") & set(elements)) > 0
        has_day = len(set("djFxs") & set(elements)) > 0
        has_hour = "H" in elements

        if has_weekday != has_weeknum and (not has_month or not has_day):
            if not has_weekday:
                elements.append("u")
            if not has_weeknum:
                elements.append("U")

        if has_hour12 != has_ampm and not has_hour:
            if not has_hour12:
                elements.append("I")
            if not has_ampm:
                elements.append("p")

        if "s" in elements:
            date = fix_year_windows(date)
            default_date = fix_year_windows(default_date)

        date_ref_elements = {
            attr: getattr(default_date, attr)
            for attr in [
                "year",
                "month",
                "day",
                "hour",
                "minute",
                "second",
                "microsecond",
                "tzinfo",
            ]
        }

        for element in elements:
            for attr in elements_attributes[element]:
                date_ref_elements[attr] = getattr(date, attr)

        # Combination of date and default_date could result in `day` being outside of
        # the valid range of the month. This is difficult to predict, so we cap at 28
        date_ref_elements["day"] = min(28, date_ref_elements["day"])
        default_date = default_date.replace(day=min(28, default_date.day))

        date_ref = dt.datetime(**date_ref_elements)

        matches = [
            GroupMatch(Group(element, 0), datetime_to_str(date_ref, element), 0, 0)
            for element in elements
        ]

        parser = DateParser(matches, default_date=default_date)
        parsed = parser.parse()
        assert parsed == date_ref

    def test_not_date_group(self) -> None:
        matches = [
            GroupMatch(Group("Y", 0), "2000", 0, 0),
            GroupMatch(Group("not_a_date_group:fmt=d", 1), "5", 0, 0),
        ]
        with pytest.raises(
            ValueError, match=r"'not_a_date_group:1' is not a date group."
        ):
            DateParser(matches).parse()

    def test_duplicate_groups(self) -> None:
        """Different groups for the same element have different values."""

        matches = [
            GroupMatch(Group("Y", 0), "2000", 0, 0),
            GroupMatch(Group("m", 1), "05", 0, 0),
            GroupMatch(Group("Y", 2), "2010", 0, 0),
        ]
        with pytest.raises(ValueError, match="Groups with the same element 'Y'"):
            DateParser(matches).parse()
