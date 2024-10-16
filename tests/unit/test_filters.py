"""Test filtering."""

from collections import abc

from filefinder.filters import Filter, FilterByDate, FilterByGroup, FilterList

# No unit testing for individual filters


def get_filter_func(name: str) -> abc.Callable[..., bool]:
    def user_func(*args, **kwargs):
        return True

    user_func.__name__ = name
    return user_func


class TestFilterList:
    def test_list(self):
        filters = FilterList()
        f1 = filters.add(get_filter_func("1"))
        f2 = filters.add(get_filter_func("2"))
        f3 = filters.add(get_filter_func("3"))

        assert len(filters) == 3

        assert filters[0] == f1
        assert filters[1] == f2
        assert filters[2] == f3

        for ref, filt in zip([f1, f2, f3], filters, strict=False):
            assert ref == filt

        filters.clear()
        assert len(filters) == 0

    def test_type(self):
        filters = FilterList()
        filt = filters.add(get_filter_func("filt"))
        filt_group = filters.add_by_group(get_filter_func("group"), [0])
        filt_date = filters.add_by_date(get_filter_func("date"))

        assert isinstance(filt, Filter)
        assert isinstance(filters[0], Filter)
        assert isinstance(filt_group, FilterByGroup)
        assert isinstance(filters[1], FilterByGroup)
        assert isinstance(filt_date, FilterByDate)
        assert isinstance(filters[2], FilterByDate)

    def test_remove_by_date(self):
        filters = FilterList()
        f1 = filters.add_by_date(get_filter_func("date1"))
        f2 = filters.add_by_date(get_filter_func("date2"))
        filters.add(get_filter_func("noise1"))
        filters.add(get_filter_func("noise2"))
        filters.add_by_group(get_filter_func("noise3"), [0, 1])
        filters.add_by_group(get_filter_func("noise4"), [0])

        filters.remove_by_date()

        assert len(filters) == 4
        assert f1 not in filters.filters
        assert f2 not in filters.filters

    def test_str(self):
        filters = FilterList()
        filters.add_by_date(get_filter_func("date1"))
        result = "<FilterByDate:date1>"

        filters.add(get_filter_func("base1"))
        result += " <Filter:base1>"

        filters.add_by_date(get_filter_func("date2"))
        result += " <FilterByDate:date2>"

        filters.add(get_filter_func("base2"))
        result += " <Filter:base2>"

        filters.add_by_group(get_filter_func("group1"), [0, 1])
        result += " <FilterByGroup:0,1:group1>"

        filters.add_by_group(get_filter_func("group2"), [0])
        result += " <FilterByGroup:0:group2>"

        assert str(filters) == result

    def test_remove_by_group(self):
        filters = FilterList()
