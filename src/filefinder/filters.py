"""Filters management."""

import datetime
import functools
import typing as t
from collections import abc

from .matches import Matches

if t.TYPE_CHECKING:
    from .finder import Finder


FilterPartial = abc.Callable[["Finder", str, Matches], bool]


class FilterFunc(t.Protocol):
    """Defines the signature of filters callables (for static type checkers).

    See `<https://mypy.readthedocs.io/en/stable/protocols.html#callback-protocols>`__
    for details.
    """

    def __call__(
        self, finder: "Finder", filename: str, matches: Matches, **kwargs: t.Any
    ) -> bool: ...


class FilterGroupFunc(t.Protocol):
    def __call__(self, __value: t.Any, **kwargs) -> bool: ...


class FilterDateFunc(t.Protocol):
    def __call__(
        self,
        __date: datetime.date,
        default_date: datetime.datetime | abc.Mapping[str, int] | None = None,
    ) -> bool: ...


class Filter:
    def __init__(
        self,
        func: FilterPartial,
        name: str | None = None,
        group_key: int | str | None = None,
    ):
        self.func: FilterPartial = func

        if name is None:
            name = getattr(func, "__name__", "")
        self.name = name

        self.group_key = group_key
        self.group_filter: bool = False

        if group_key is not None:
            self.group_filter = True
            self.name = f"{group_key}: {self.name}"

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"

    def execute(self, finder: "Finder", filename: str, matches: Matches) -> bool:
        return self.func(finder, filename, matches)


class FilterList:
    def __init__(self) -> None:
        self.filters: list[Filter] = []

    def __getitem__(self, key: int) -> Filter:
        return self.filters[key]

    def __len__(self) -> int:
        return len(self.filters)

    def __iter__(self) -> abc.Iterator[Filter]:
        return iter(self.filters)

    def add(self, func: FilterFunc, name: str | None = None, **kwargs) -> Filter:
        partial = functools.partial(func, **kwargs)
        filt = Filter(partial, name=name)
        self.filters.append(filt)
        return filt

    def add_by_group(
        self,
        func: FilterGroupFunc,
        key: int | str,
        name: str | None = None,
        fix_discard: bool = False,
        pass_unparsed: bool = False,
        **kwargs,
    ) -> Filter:
        def filt(finder: "Finder", filename: str, matches: Matches, **kwargs):
            values: list[t.Any] = []
            for m in matches.get_matches(key, keep_discard=fix_discard):
                if not m.can_parse() and pass_unparsed:
                    values.append(m.match_str)
                else:
                    values.append(m.match_parsed)

            return all(func(v, **kwargs) for v in values)

        if name is None:
            name = getattr(func, "__name__", None)

        return self.add(filt, group_key=key, name=name, **kwargs)

    def add_by_date(
        self,
        func: FilterDateFunc,
        name: str | None = None,
        **kwargs,
    ) -> Filter:
        def filt_date(finder: "Finder", filename: str, matches: Matches, **kwargs):
            date = matches.get_date(**kwargs)
            return func(date)

        if name is None:
            name = getattr(func, "__name__", None)

        return self.add(filt_date, group_key="date", name=name, **kwargs)

    def clear(self):
        self.filters.clear()

    def remove_by_group(self, key: int | str):
        self.filters = [filt for filt in self.filters if filt.group_key == key]
