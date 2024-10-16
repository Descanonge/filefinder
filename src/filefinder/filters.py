"""Filters management."""

import datetime
import functools
import typing as t
from collections import abc

from .matches import DefaultDate, Matches

if t.TYPE_CHECKING:
    from .finder import Finder


class UserFunc(t.Protocol):
    def __call__(
        self, finder: "Finder", filename: str, matches: Matches, **kwargs
    ) -> bool: ...


class UserFuncGroup(t.Protocol):
    def __call__(self, __value: t.Any, **kwargs) -> bool: ...


class UserFuncDate(UserFuncGroup, t.Protocol):
    def __call__(
        self,
        __date: datetime.date,
        default_date: datetime.datetime | abc.Mapping[str, int] | None = None,
        **kwargs,
    ) -> bool: ...


FilterFunc = abc.Callable[["Finder", str, Matches], bool]
UserFuncGroupPartial = abc.Callable[[t.Any], bool]
UserFuncDatePartial = abc.Callable[[datetime.date], bool]


class Filter:
    user_func: abc.Callable[..., bool]
    partial_func: abc.Callable[..., bool]
    filter_func: FilterFunc

    def __init__(self, func: abc.Callable[..., bool], **kwargs):
        self.user_func = func
        self.partial_func = self.get_partial_func(**kwargs)
        self.filter_func = self.get_filter_func()
        self.name = self._get_name()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__} {self.name}>"

    def execute(self, finder: "Finder", filename: str, matches: Matches) -> bool:
        return self.filter_func(finder, filename, matches)

    def _get_name(self) -> str:
        return getattr(self.user_func, "__name__", "")

    def get_partial_func(self, **kwargs) -> abc.Callable[..., bool]:
        if kwargs:
            return functools.partial(self.user_func, **kwargs)
        return self.user_func

    def get_filter_func(self) -> FilterFunc:
        return self.partial_func


class FilterByGroup(Filter):
    user_func: UserFuncGroup
    partial_func: UserFuncGroupPartial
    indices: list[int]
    pass_unparsed: bool

    def __init__(
        self,
        user_func: UserFuncGroup | UserFuncGroupPartial,
        indices: abc.Sequence[int],
        pass_unparsed: bool = False,
        **kwargs,
    ):
        self.indices = list(indices)
        self.pass_unparsed = pass_unparsed
        super().__init__(user_func, **kwargs)

    def _get_name(self) -> str:
        name = super()._get_name()
        indices = ",".join(map(str, self.indices))
        name = f"{indices} {name}"
        return name

    def get_filter_func(self) -> FilterFunc:
        def filt(finder: "Finder", filename: str, matches: Matches) -> bool:
            values: list[t.Any] = []
            for i in self.indices:
                m = matches.matches[i]
                if not m.can_parse() and self.pass_unparsed:
                    values.append(m.match_str)
                else:
                    values.append(m.match_parsed)

            return all(self.partial_func(v) for v in values)

        return filt

    def reset(self):
        self.filter_func = self.get_filter_func()
        self.name = self._get_name()


class FilterByDate(Filter):
    user_func: UserFuncDate
    partial_func: UserFuncDatePartial
    default_date: DefaultDate = None

    def __init__(
        self,
        *args,
        default_date: DefaultDate = None,
        **kwargs,
    ):
        self.default_date = default_date
        super().__init__(*args, **kwargs)

    def _get_name(self) -> str:
        return "date " + super()._get_name()

    def get_filter_func(self) -> FilterFunc:
        def filt(finder: "Finder", filename: str, matches: Matches) -> bool:
            date = matches.get_date(default_date=self.default_date)
            return self.partial_func(date)

        return filt


class FilterList:
    def __init__(self) -> None:
        self.filters: list[Filter] = []

    def __getitem__(self, key: int) -> Filter:
        return self.filters[key]

    def __len__(self) -> int:
        return len(self.filters)

    def __iter__(self) -> abc.Iterator[Filter]:
        return iter(self.filters)

    def is_valid(self, finder: "Finder", filename: str, matches: Matches) -> bool:
        return all(filt.execute(finder, filename, matches) for filt in self)

    def add(self, func: FilterFunc, **kwargs) -> Filter:
        filt = Filter(func, **kwargs)
        self.filters.append(filt)
        return filt

    def add_by_group(
        self,
        func: UserFuncGroup,
        indices: abc.Sequence[int],
        pass_unparsed: bool = False,
        **kwargs,
    ) -> FilterByGroup:
        filt = FilterByGroup(func, indices, pass_unparsed=pass_unparsed)
        self.filters.append(filt)
        return filt

    def add_by_date(
        self,
        func: UserFuncDate,
        default_date: DefaultDate = None,
        **kwargs,
    ) -> FilterByDate:
        filt = FilterByDate(func, default_date=default_date, **kwargs)
        self.filters.append(filt)
        return filt

    def clear(self):
        self.filters.clear()

    def remove_by_group(self, indices: abc.Sequence[int]):
        filters = []
        for filt in self.filters:
            if isinstance(filt, FilterByGroup):
                new_indices = [i for i in filt.indices if i not in indices]
                if not new_indices:
                    continue
                filt.indices = new_indices
                filt.reset()
            filters.append(filt)
        self.filters = filters

    def remove_by_date(self):
        self.filters = [
            filt for filt in self.filters if not isinstance(filt, FilterByDate)
        ]
