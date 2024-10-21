"""Test filtering."""

import typing as t
from collections import abc

from filefinder.filters import Filter, FilterByDate, FilterByGroup, FilterList
from filefinder.group import Group
from filefinder.matches import Match, Matches

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
        base = filters.add(get_filter_func("base"))
        group1 = filters.add_by_group(get_filter_func("group1"), [0, 1, 2, 3])
        group2 = filters.add_by_group(get_filter_func("group2"), [0, 1])
        group3 = filters.add_by_group(get_filter_func("group3"), [0])
        date = filters.add_by_date(get_filter_func("date"))

        filters.remove_by_group([0, 2])
        assert group1.indices == [1, 3]
        assert group2.indices == [1]
        assert group3 not in filters
        for filt in [base, group1, group2, date]:
            assert filt in filters

        filters.remove_by_group([1])
        assert group1.indices == [3]
        assert group2 not in filters
        for filt in [base, group1, date]:
            assert filt in filters


class TestFilterExecute:
    @staticmethod
    def is_positive(x: int) -> bool:
        return x > 0

    def get_matches(
        self, groups: abc.Sequence[Group], values: abc.Sequence[t.Any]
    ) -> Matches:
        matches = [
            Match(group, str(value), -1, -1)
            for group, value in zip(groups, values, strict=True)
        ]
        return Matches(matches, groups)

    def get_int_groups(self, length: int) -> list[Group]:
        return [Group(f"{chr(97+i)}:fmt=d", i) for i in range(length)]

    def test_simple(self):
        def func(finder, filename: str, matches) -> bool:
            return filename.isupper()

        filt = Filter(func)

        assert filt.is_valid(None, "ABC", None)
        assert not filt.is_valid(None, "abc", None)

    def test_kwargs(self):
        def func(finder, filename: str, matches, legal: list[str]) -> bool:
            return filename in legal

        filt = Filter(func, legal=["a", "b"])
        assert filt.is_valid(None, "a", None)
        assert not filt.is_valid(None, "c", None)

        filt = Filter(func, legal=["b", "c"])
        assert not filt.is_valid(None, "a", None)
        assert filt.is_valid(None, "c", None)

    def test_by_group(self):
        groups = self.get_int_groups(3)

        def is_valid(indices: list[int], values: list[int]) -> bool:
            filt = FilterByGroup(self.is_positive, indices)
            matches = self.get_matches(groups, values)
            return filt.is_valid(None, "", matches)

        assert is_valid([2], [0, 0, 1])
        assert not is_valid([2], [0, 0, -1])
        assert not is_valid([2], [5, 5, -1])

        assert is_valid([0, 2], [1, 0, 1])
        assert not is_valid([0, 2], [1, 2, -1])

    def test_multiple_by_group(self):
        groups = self.get_int_groups(3)

        filters = FilterList()

        def is_valid(values: list[int]) -> bool:
            matches = self.get_matches(groups, values)
            return filters.is_valid(None, "", matches)

        filters.add_by_group(self.is_positive, [0])
        assert is_valid([2, 0, 0])
        assert not is_valid([0, 0, 0])

        filters.add_by_group(self.is_positive, [2])
        assert not is_valid([2, 0, 0])
        assert not is_valid([0, 0, 0])
        assert is_valid([5, 0, 2])

    def test_by_group_change(self):
        groups = self.get_int_groups(3)

        filters = FilterList()

        def is_valid(values: list[int]) -> bool:
            matches = self.get_matches(groups, values)
            return filters.is_valid(None, "", matches)

        filters.add_by_group(self.is_positive, [0, 2])
        assert is_valid([1, 0, 1])
        assert is_valid([1, 1, 1])

        filters.remove_by_group([2])
        assert is_valid([1, 0, 0])
        assert not is_valid([0, 0, 2])
