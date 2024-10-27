"""Test library functions.

Presentely, only `library.get_date`.
"""

import os
from datetime import datetime, timedelta

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from util import FilesDefinition, time_segments

import filefinder.library
from filefinder.finder import Finder
from filefinder.util import (
    date_from_doy,
    datetime_to_str,
    datetime_to_value,
    get_doy,
    name_to_date,
)


class TestDatetimeUtil:
    def test_datetime_to_str(self):
        date = datetime(2086, 3, 2, 1, 34, 6)
        assert datetime_to_str(date, "Y") == "2086"
        assert datetime_to_str(date, "m") == "03"
        assert datetime_to_str(date, "d") == "02"
        assert datetime_to_str(date, "B") == "March"
        assert datetime_to_str(date, "x") == "20860302"
        assert datetime_to_str(date, "F") == "2086-03-02"
        assert datetime_to_str(date, "H") == "01"
        assert datetime_to_str(date, "M") == "34"
        assert datetime_to_str(date, "S") == "06"
        assert datetime_to_str(date, "X") == "013406"

    @given(date=st.datetimes())
    def test_datetime_to_value(self, date: datetime):
        assert datetime_to_value(date, "Y") == date.year
        assert datetime_to_value(date, "m") == date.month
        assert datetime_to_value(date, "d") == date.day
        assert datetime_to_value(date, "H") == date.hour
        assert datetime_to_value(date, "M") == date.minute
        assert datetime_to_value(date, "S") == date.second

        for name in "FxXB":
            assert datetime_to_value(date, name) == datetime_to_str(date, name)

    def test_get_doy(self):
        assert get_doy(datetime(2004, 1, 1)) == 1
        assert get_doy(datetime(2004, 1, 2)) == 2
        assert get_doy(datetime(2004, 2, 1)) == 32
        assert get_doy(datetime(2004, 3, 1)) == 61
        assert get_doy(datetime(2005, 3, 1)) == 60

    def test_date_from_doy(self):
        assert date_from_doy(1, 2004) == dict(month=1, day=1)
        assert date_from_doy(2, 2004) == dict(month=1, day=2)
        assert date_from_doy(32, 2004) == dict(month=2, day=1)
        assert date_from_doy(61, 2004) == dict(month=3, day=1)
        assert date_from_doy(60, 2005) == dict(month=3, day=1)

    @given(date=st.datetimes())
    def test_date_to_doy_and_back(self, date: datetime):
        doy = get_doy(date)
        back = date_from_doy(doy, date.year)
        assert back["month"] == date.month
        assert back["day"] == date.day

    @given(doy=st.integers(1, 365), year=st.integers(1, 3000))
    def test_doy_to_date_and_back(self, doy: int, year: int):
        elts = date_from_doy(doy, year)
        date = datetime(year, elts["month"], elts["day"])
        back = get_doy(date)
        assert doy == back


class TestDateRecovery:
    @settings(
        suppress_health_check=[HealthCheck.function_scoped_fixture], deadline=None
    )
    @given(segments=time_segments(), date=st.datetimes(), default_date=st.datetimes())
    def test_get_date(
        self, segments: list[str], date: datetime, default_date: datetime
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
            for elt in name_to_date[name]:
                elements[elt] = getattr(date, elt)
                elements_specified.add(elt)

        try:
            date_ref = datetime(**elements)
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
    def setup_test(self, fs) -> tuple[FilesDefinition, Finder]:
        dates = [datetime(2000, 1, 1) + i * timedelta(days=1) for i in range(365)]
        params = list(range(20))
        fd = FilesDefinition(fs, dates=dates, params=params, create=True)
        finder = Finder(
            fd.datadir,
            "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:bool=_yes).ext",
        )
        return fd, finder

    def test_filter_dates(self, fs):
        fd, finder = self.setup_test(fs)

        finder.add_filter(
            filefinder.library.filter_date_range, start="2000-01-01", stop="2000-01-02"
        )
        ndays = 2
        assert len(finder.files) == ndays * len(fd.params) * 2

        finder.clear_filters()
        finder.add_filter(
            filefinder.library.filter_date_range, start="2000-05-10", stop="2000-06-10"
        )
        ndays = 32
        assert_nfiles(finder, ndays * 2 * len(fd.params))

        finder.fix_groups(m=[5, 6])
        finder.clear_filters()
        finder.add_filter(
            filefinder.library.filter_date_range,
            start=datetime(2000, 5, 10),
            stop=datetime(2000, 6, 10),
        )
        assert_nfiles(finder, ndays * 2 * len(fd.params))

        finder.fix_groups(m=2)
        assert_nfiles(finder, 0)

    def test_fix_by_filter_dates(self, fs):
        fd, finder = self.setup_test(fs)

        finder.fix_by_filter(
            "date", lambda d: datetime(2000, 1, 1) <= d <= datetime(2000, 1, 2)
        )
        ndays = 2
        assert_nfiles(finder, ndays * len(fd.params) * 2)

        finder.clear_filters()
        finder.fix_by_filter(
            "date", lambda d: datetime(2000, 5, 10) <= d <= datetime(2000, 6, 10)
        )
        ndays = 32
        assert_nfiles(finder, ndays * len(fd.params) * 2)
        assert len(finder.files) == ndays * len(fd.params) * 2

        finder.fix_groups(m=[5, 6])
        finder.clear_filters()
        finder.fix_by_filter(
            "date", lambda d: datetime(2000, 5, 10) <= d <= datetime(2000, 6, 10)
        )
        assert_nfiles(finder, ndays * len(fd.params) * 2)

        finder.fix_groups(m=2)
        assert_nfiles(finder, 0)

        finder.clear_filters()
        finder.unfix_groups()
        finder.fix_by_filter("date", lambda d: d.month % 2 == 0)
        ndays = 181
        assert_nfiles(finder, ndays * len(fd.params) * 2)

    def test_filter_values(self, fs):
        fd, finder = self.setup_test(fs)

        finder.add_filter(filefinder.library.filter_by_range, group="param", min=5)
        nvalues = 19 - 5 + 1
        assert len(finder.files) == 2 * len(fd.dates) * nvalues

        finder.add_filter(filefinder.library.filter_by_range, group="param", max=10)
        nvalues = 10 - 5 + 1
        assert_nfiles(finder, 2 * len(fd.dates) * nvalues)

        finder.clear_filters()
        finder.add_filter(
            filefinder.library.filter_by_range, group="param", min=10, max=15
        )
        nvalues = 15 - 10 + 1
        assert_nfiles(finder, 2 * len(fd.dates) * nvalues)

    def test_filter_group(self, fs):
        fd, finder = self.setup_test(fs)

        finder.fix_by_filter("m", lambda m: m == 12)
        assert len(finder.files) == 30 * len(fd.params) * 2

        finder.fix_by_filter("option", bool)
        assert_nfiles(finder, 30 * len(fd.params))

        # test unfixing
        finder.unfix_groups("m")
        assert_nfiles(finder, len(fd.dates) * len(fd.params))

        finder.fix_by_filter("param", lambda x: x < 10)
        assert_nfiles(finder, len(fd.dates) * 10)

        finder.fix_by_filter("param", lambda x: x % 2 == 0)
        assert_nfiles(finder, len(fd.dates) * 5)
