"""Test date related functions."""

import calendar
import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from hypothesis import example, given
from hypothesis import strategies as st
from lib import Drawer

from filefinder.dates import (
    DATETIME_ELEMENTS,
    STRING_ELEMENTS,
    TIME_ELEMENTS,
    DateParser,
    _datetime_to_dict,
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
        date=st.datetimes(
            min_value=dt.datetime(1800, 1, 1), max_value=dt.datetime(2200, 1, 1)
        ),
        tz=st.one_of(st.none(), st_tzinfo()),
    )
    def test_process_s(self, date: dt.datetime, tz: dt.timezone | None) -> None:
        if tz is None:
            tz = dt.UTC
        date = date.replace(tzinfo=tz)

        matches = [GroupMatch(Group("s", 0), str(date.timestamp()), 0, 0)]
        if tz is not None:
            matches.append(GroupMatch(Group("z", 0), date.strftime("%z"), 0, 0))

        parser = DateParser(matches)

        if tz is not None:
            parser.process("z", parser.process_z)

        assert parser.process_s() == _datetime_to_dict(date)

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

    @given(tz=st_tzinfo())
    def test_process_z_elements(self, tz: dt.timezone) -> None:
        date = dt.datetime(2000, 1, 1, tzinfo=tz)
        gm = GroupMatch(Group("z", 0), date.strftime("%z"), 0, 0)
        parser = DateParser([gm])

        assert parser.process_z() == {"tzinfo": tz}

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

    @given(date=st.datetimes(), tzinfo=st.one_of(st.timezones(), st_tzinfo()))
    def test_parse(self, date: dt.datetime, tzinfo: dt.timezone) -> None:
        """Test parsing a date from all elements."""
        # convert to timedelta based, otherwise comparison will fail
        tzdelta = tzinfo.utcoffset(date)

        if not 1800 < date.year < 2200:
            # timestamp breaks at the microsecond level
            date = date.replace(microsecond=0)
            tzdelta -= dt.timedelta(microseconds=tzdelta.microseconds)

        date = date.replace(tzinfo=dt.timezone(tzdelta))

        matches = [
            GroupMatch(Group(name, 0), datetime_to_str(date, name), 0, 0)
            for name in DATETIME_ELEMENTS
        ]
        assert DateParser.parse(matches) == date

        # alternative way
        parser = DateParser(matches)
        assert parser.retrieve_date() == date

    @given(
        date=st.datetimes(
            min_value=dt.datetime(1800, 1, 1),
            max_value=dt.datetime(2200, 1, 1),
            timezones=st.one_of(st.timezones(), st_tzinfo()),
        ),
        default_date=st.datetimes(timezones=st.one_of(st.none(), st.timezones())),
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
        has_weeknum = len(set("UW") & set(elements)) > 0
        has_month = len(set("bBmjFxs") & set(elements)) > 0
        has_day = len(set("djFxs") & set(elements)) > 0

        if has_ampm != has_hour12:
            with pytest.raises(ValueError):
                DateParser.parse(matches)
            return

        if has_weekday != has_weeknum:
            # try specifying what is missing with default_date
            default_date_with_missing = _datetime_to_dict(default_date)
            if not has_weeknum:
                default_date_with_missing["weeknumber"] = int(date_ref.strftime("%W"))
            if not has_weekday:
                default_date_with_missing["weekday"] = int(date_ref.strftime("%w"))

            parser = DateParser(matches, default_date=default_date_with_missing)
            parsed = parser.retrieve_date()
            assert parsed == date_ref

            if not has_month or not has_day:
                with pytest.raises(ValueError):
                    DateParser.parse(matches)
                return

        parser = DateParser(matches, default_date=default_date)
        parsed = parser.retrieve_date()
        assert parsed == date_ref

    def test_not_date_group(self) -> None:
        matches = [
            GroupMatch(Group("Y", 0), "2000", 0, 0),
            GroupMatch(Group("not_a_date_group:fmt=d", 1), "5", 0, 0),
        ]
        with pytest.raises(
            ValueError, match=r"'not_a_date_group:1' is not a date group."
        ):
            DateParser.parse(matches)

    def test_duplicate_groups(self) -> None:
        """Different groups for the same element have different values."""

        matches = [
            GroupMatch(Group("Y", 0), "2000", 0, 0),
            GroupMatch(Group("m", 1), "05", 0, 0),
            GroupMatch(Group("Y", 2), "2010", 0, 0),
        ]
        with pytest.raises(ValueError, match="Groups with the same element 'Y'"):
            DateParser.parse(matches)
