"""Test filtering."""

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from filefinder.filters import Filter, FilterByDate, FilterByGroup, FilterList
from filefinder.finder import Finder
from filefinder.group import Group
from filefinder.matches import FileMatch, GroupMatch


def get_filter_func(name: str) -> Callable[..., bool]:
    def user_func(*args: Any, **kwargs: Any) -> bool:  # noqa: ARG001
        return True

    user_func.__name__ = name
    return user_func


class TestFilterList:
    def test_list(self) -> None:
        """Test containerish methods."""
        filters = FilterList()
        f1 = filters.add(get_filter_func("1"))
        f2 = filters.add(get_filter_func("2"))
        f3 = filters.add(get_filter_func("3"))

        # __len__
        assert len(filters) == 3

        # __getitem__
        assert filters[0] == f1
        assert filters[1] == f2
        assert filters[2] == f3

        # __contains__
        assert f1 in filters
        assert f3 in filters
        assert None not in filters

        # __iter__
        for ref, filt in zip([f1, f2, f3], filters, strict=False):
            assert ref == filt

        # clear
        filters.clear()
        assert len(filters) == 0

    def test_type(self) -> None:
        filters = FilterList()
        filt = filters.add(get_filter_func("filt"))
        filt_group = filters.add_by_group(get_filter_func("group"), [0])
        filt_date = filters.add_by_date(get_filter_func("date"), "date")

        assert isinstance(filt, Filter)
        assert isinstance(filters[0], Filter)
        assert isinstance(filt_group, FilterByGroup)
        assert isinstance(filters[1], FilterByGroup)
        assert isinstance(filt_date, FilterByDate)
        assert isinstance(filters[2], FilterByDate)

    def test_remove_by_date(self) -> None:
        filters = FilterList()
        f1 = filters.add_by_date(get_filter_func("date1"), "date1")
        f2 = filters.add_by_date(get_filter_func("date2"), "date2")
        filters.add(get_filter_func("noise1"))
        filters.add(get_filter_func("noise2"))
        filters.add_by_group(get_filter_func("noise3"), [0, 1])
        filters.add_by_group(get_filter_func("noise4"), [0])

        filters.remove_by_date("date1")

        assert len(filters) == 5
        assert f1 not in filters.filters
        assert f2 in filters.filters

    def test_str(self) -> None:
        filters = FilterList()
        filters.add_by_date(get_filter_func("date1"), "date1")
        result = "<FilterByDate:date1>"

        filters.add(get_filter_func("base1"))
        result += " <Filter:base1>"

        filters.add_by_date(get_filter_func("date2"), "date2")
        result += " <FilterByDate:date2>"

        filters.add(get_filter_func("base2"))
        result += " <Filter:base2>"

        filters.add_by_group(get_filter_func("group1"), [0, 1])
        result += " <FilterByGroup:0,1:group1>"

        filters.add_by_group(get_filter_func("group2"), [0])
        result += " <FilterByGroup:0:group2>"

        assert str(filters) == result

    def test_remove_by_group(self) -> None:
        filters = FilterList()
        base = filters.add(get_filter_func("base"))
        group1 = filters.add_by_group(get_filter_func("group1"), [0, 1, 2, 3])
        group2 = filters.add_by_group(get_filter_func("group2"), [0, 1])
        group3 = filters.add_by_group(get_filter_func("group3"), [0])
        date = filters.add_by_date(get_filter_func("date"), "date")

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


def is_positive(x: int) -> bool:
    return x > 0


def is_valid(filt: Filter | FilterList, filematch: FileMatch) -> bool:
    return filt.is_valid(None, filematch)  # type: ignore[arg-type]


class TestFilterExecute:
    def get_filematch(
        self, filename: str, groups: Sequence[Group], values: Sequence[Any]
    ) -> FileMatch:
        matches = [
            GroupMatch(group, str(value), -1, -1)
            for group, value in zip(groups, values, strict=True)
        ]
        return FileMatch(Path(), Path(filename), matches, groups)

    def get_int_groups(self, length: int) -> list[Group]:
        return [Group(f"{chr(97 + i)}:fmt=d", i) for i in range(length)]

    def test_simple(self) -> None:
        def func(finder: Finder, filematch: FileMatch) -> bool:  # noqa: ARG001
            return str(filematch.filename).isupper()

        filt = Filter(func)
        assert is_valid(filt, FileMatch(Path(), Path("ABC"), [], []))
        assert not is_valid(filt, FileMatch(Path(), Path("abc"), [], []))

    def test_kwargs(self) -> None:
        def func(finder: Finder, filematch: FileMatch, legal: list[str]) -> bool:  # noqa: ARG001
            return str(filematch.filename) in legal

        filt = Filter(func, legal=["a", "b"])
        assert is_valid(filt, FileMatch(Path(), Path("a"), [], []))
        assert not is_valid(filt, FileMatch(Path(), Path("c"), [], []))

        filt = Filter(func, legal=["b", "c"])
        assert not is_valid(filt, FileMatch(Path(), Path("a"), [], []))
        assert is_valid(filt, FileMatch(Path(), Path("c"), [], []))

    def test_by_group(self) -> None:
        groups = self.get_int_groups(3)

        def is_valid_(indices: list[int], values: list[int]) -> bool:
            filt = FilterByGroup(is_positive, indices)
            filematch = self.get_filematch("", groups, values)
            return is_valid(filt, filematch)

        assert is_valid_([2], [0, 0, 1])
        assert not is_valid_([2], [0, 0, -1])
        assert not is_valid_([2], [5, 5, -1])

        assert is_valid_([0, 2], [1, 0, 1])
        assert not is_valid_([0, 2], [1, 2, -1])

    def test_multiple_by_group(self) -> None:
        groups = self.get_int_groups(3)

        filters = FilterList()

        def is_valid_(values: list[int]) -> bool:
            filematch = self.get_filematch("", groups, values)
            return is_valid(filters, filematch)

        filters.add_by_group(is_positive, [0])
        assert is_valid_([2, 0, 0])
        assert not is_valid_([0, 0, 0])

        filters.add_by_group(is_positive, [2])
        assert not is_valid_([2, 0, 0])
        assert not is_valid_([0, 0, 0])
        assert is_valid_([5, 0, 2])

    def test_by_group_change(self) -> None:
        groups = self.get_int_groups(3)

        filters = FilterList()

        def is_valid_(values: list[int]) -> bool:
            matches = self.get_filematch("", groups, values)
            return is_valid(filters, matches)

        filters.add_by_group(is_positive, [0, 2])
        assert is_valid_([1, 0, 1])
        assert is_valid_([1, 1, 1])

        filters.remove_by_group([2])
        assert is_valid_([1, 0, 0])
        assert not is_valid_([0, 0, 2])
