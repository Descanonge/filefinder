"""Test library functions.

Presentely, only `library.get_date`.
"""

# ruff: noqa: PLR2004

import datetime as dt
import os
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from util import FilesDefinitionAuto, time_segments

import filefinder.library
from filefinder.finder import Finder
from filefinder.util import (
    date_from_doy,
    datetime_attributes,
    datetime_to_str,
    datetime_to_value,
    get_doy,
)


class TestDatetimeUtil:
    def test_datetime_to_str(self):
        date = dt.datetime(2086, 3, 2, 1, 34, 6)
        assert datetime_to_str(date, "Y") == "2086"
        assert datetime_to_str(date, "m") == "03"
        assert datetime_to_str(date, "d") == "02"
        assert datetime_to_str(date, "B") == "March"

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

    def test_datetime_to_value_basic(self):
        date = dt.datetime(2086, 3, 2, 1, 34, 6)
        assert datetime_to_value(date, "Y") == 2086
        assert datetime_to_value(date, "m") == 3
        assert datetime_to_value(date, "d") == 2
        assert datetime_to_value(date, "B") == "March"

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
    def test_datetime_to_value(self, date: dt.datetime):
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

    def test_get_doy(self):
        assert get_doy(dt.datetime(2004, 1, 1)) == 1
        assert get_doy(dt.datetime(2004, 1, 2)) == 2
        assert get_doy(dt.datetime(2004, 2, 1)) == 32
        assert get_doy(dt.datetime(2004, 3, 1)) == 61
        assert get_doy(dt.datetime(2005, 3, 1)) == 60

    def test_date_from_doy(self):
        assert date_from_doy(1, 2004) == dict(month=1, day=1)
        assert date_from_doy(2, 2004) == dict(month=1, day=2)
        assert date_from_doy(32, 2004) == dict(month=2, day=1)
        assert date_from_doy(61, 2004) == dict(month=3, day=1)
        assert date_from_doy(60, 2005) == dict(month=3, day=1)

    @given(date=st.datetimes())
    def test_date_to_doy_and_back(self, date: dt.datetime):
        doy = get_doy(date)
        back = date_from_doy(doy, date.year)
        assert back["month"] == date.month
        assert back["day"] == date.day

    @given(doy=st.integers(1, 365), year=st.integers(1, 3000))
    def test_doy_to_date_and_back(self, doy: int, year: int):
        elts = date_from_doy(doy, year)
        date = dt.datetime(year, elts["month"], elts["day"])
        back = get_doy(date)
        assert doy == back


class TestDateRecovery:
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
    )
    @given(segments=time_segments(), date=st.datetimes(), default_date=st.datetimes())
    def test_get_date(
        self, segments: list[str], date: dt.datetime, default_date: dt.datetime
    ):
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
            for attr in datetime_attributes[name]:
                elements[attr] = getattr(date, attr)
                elements_specified.add(attr)

        try:
            date_ref = dt.datetime(**elements)
        except ValueError:
            # from combining elements and default date, we might have a day value that
            # is too high for the month
            return

        for i, name in enumerate(group_names):
            segments[2 * i + 1] = datetime_to_str(date_ref, name)

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

    def test_invalid_file_differing_elements(self):
        finder = Finder("", "%(Y)/%(m)/%(F).ext")
        filenames = ["2005/01/2006-01-02.ext", "2005/01/2005-03-01.ext"]
        filenames = [f.replace("/", os.sep) for f in filenames]
        for f in filenames:
            with pytest.raises(ValueError):
                filefinder.library.get_date(finder.find_matches(f))

    def test_no_date_matchers(self, caplog):
        finder = Finder("", r"%(year:fmt=02d)/%(month:fmt=02d)/%(full:fmt=s).ext")
        filenames = ["2005/01/2006-01-02.ext", "2005/01/2005-03-01.ext"]
        filenames = [f.replace("/", os.sep) for f in filenames]
        for f in filenames:
            finder.find_matches(f).get_date()
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


class TestFilters:
    fd: FilesDefinitionAuto
    finder: Finder

    def setup_test(self, tmp_path: Path):
        self.fd = FilesDefinitionAuto(
            tmp_path,
            dates=[
                dt.datetime(2000, 1, 1) + i * dt.timedelta(days=1) for i in range(365)
            ],
            params=list(range(20)),
            create=True,
        )

        for i in range(20):
            self.fd.create_file(os.path.join(self.fd.datadir, f"invalid_files_{i}.ext"))

        self.finder = Finder(
            self.fd.get_absolute(self.fd.datadir),
            "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
        )
        assert len(self.finder.files) == len(self.fd.files)

        return self.fd.dates, self.fd.params, self.fd.options

    def test_filter_dates(self, tmp_path: Path):
        dates, params, options = self.setup_test(tmp_path)
        ndays = len(dates)
        nparams = len(params)
        noptions = len(options)

        self.finder.add_filter(
            filefinder.library.filter_date_range, start="2000-01-01", stop="2000-01-02"
        )
        ndays = 2
        assert len(self.finder.files) == ndays * nparams * noptions

        self.finder.clear_filters()
        self.finder.add_filter(
            filefinder.library.filter_date_range, start="2000-05-10", stop="2000-06-10"
        )
        ndays = 32
        assert_nfiles(self.finder, ndays * nparams * noptions)

        self.finder.fix_groups(m=[5, 6])
        self.finder.clear_filters()
        self.finder.add_filter(
            filefinder.library.filter_date_range,
            start=dt.datetime(2000, 5, 10),
            stop=dt.datetime(2000, 6, 10),
        )
        assert_nfiles(self.finder, ndays * nparams * noptions)

        self.finder.fix_groups(m=2)
        assert_nfiles(self.finder, 0)

    def test_fix_by_filter_dates(self, tmp_path: Path):
        dates, params, options = self.setup_test(tmp_path)
        ndays = len(dates)
        nparams = len(params)
        noptions = len(options)

        self.finder.fix_by_filter(
            "date", lambda d: dt.datetime(2000, 1, 1) <= d <= dt.datetime(2000, 1, 2)
        )
        ndays = 2
        assert_nfiles(self.finder, ndays * nparams * noptions)

        self.finder.clear_filters()
        self.finder.fix_by_filter(
            "date", lambda d: dt.datetime(2000, 5, 10) <= d <= dt.datetime(2000, 6, 10)
        )
        ndays = 32
        assert_nfiles(self.finder, ndays * len(params) * 2)
        assert len(self.finder.files) == ndays * nparams * noptions

        self.finder.fix_groups(m=[5, 6])
        self.finder.clear_filters()
        self.finder.fix_by_filter(
            "date", lambda d: dt.datetime(2000, 5, 10) <= d <= dt.datetime(2000, 6, 10)
        )
        assert_nfiles(self.finder, ndays * nparams * noptions)

        self.finder.fix_groups(m=2)
        assert_nfiles(self.finder, 0)

        self.finder.clear_filters()
        self.finder.unfix_groups()
        self.finder.fix_by_filter("date", lambda d: d.month % 2 == 0)
        ndays = 181
        assert_nfiles(self.finder, ndays * nparams * noptions)

    def test_filter_values(self, tmp_path: Path):
        dates, params, options = self.setup_test(tmp_path)
        ndays = len(dates)
        nparams = len(params)
        noptions = len(options)

        self.finder.add_filter(filefinder.library.filter_by_range, group="param", min=5)
        nparams = 19 - 5 + 1
        assert len(self.finder.files) == ndays * nparams * noptions

        self.finder.add_filter(
            filefinder.library.filter_by_range, group="param", max=10
        )
        nparams = 10 - 5 + 1
        assert_nfiles(self.finder, ndays * nparams * noptions)

        self.finder.clear_filters()
        self.finder.add_filter(
            filefinder.library.filter_by_range, group="param", min=10, max=15
        )
        nparams = 15 - 10 + 1
        assert_nfiles(self.finder, ndays * nparams * noptions)

    def test_filter_group(self, tmp_path: Path):
        dates, params, options = self.setup_test(tmp_path)
        ndays = len(dates)
        nparams = len(params)
        noptions = len(options)

        self.finder.fix_by_filter("m", lambda m: m == 12)
        ndays = 30
        assert len(self.finder.files) == ndays * nparams * noptions

        self.finder.fix_by_filter("option", bool)
        assert_nfiles(self.finder, ndays * nparams)

        # test unfixing
        self.finder.unfix_groups("m")
        ndays = len(dates)
        assert_nfiles(self.finder, ndays * nparams)

        self.finder.fix_by_filter("param", lambda x: x < 10)
        nparams = 10
        assert_nfiles(self.finder, ndays * nparams)

        self.finder.fix_by_filter("param", lambda x: x % 2 == 0)
        nparams = 5
        assert_nfiles(self.finder, ndays * nparams)
