"""Filters management."""

import datetime
import functools
import typing as t
from collections import abc

from .matches import DefaultDate, Matches

if t.TYPE_CHECKING:
    from .finder import Finder


class UserFunc(t.Protocol):
    """Signature of function that can be supplied to be used as a filter.

    .. py:function:: basic_filter(finder, filename, matches, **kwargs)
        :no-index:

        :param Finder finder: The finder object.
        :param str filename: The filename to keep or discard.
        :param Matches matches: The matches associated to this filename.
        :param ~typing.Any kwargs: Additional keywords passed to the filter.

        :returns: True if `filename` is to be kept, False otherwise.
    """

    def __call__(  # noqa: D102
        self, finder: "Finder", filename: str, matches: Matches, **kwargs
    ) -> bool: ...


class UserFuncGroup(t.Protocol):
    """Signature of function that can used as a filter for specific groups.

    .. py:function:: group_filter(value, **kwargs)
        :no-index:

        :param ~typing.Any value: The value parsed.
        :param ~typing.Any kwargs: Additional keywords passed to the filter.

        :returns: True if the file is to be kept, False otherwise.
    """

    def __call__(self, __value: t.Any, **kwargs) -> bool: ...  # noqa: D102


class UserFuncDate(UserFuncGroup, t.Protocol):
    """Signature of function that can used as a filter for the date pseudo-group.

    .. py:function:: date_filter(date, default_date=None, **kwargs)
        :no-index:

        :param datetime.date date: The date parsed.
        :param datetime.date | ~collections.abc.Mapping[str, int] | None default_date:
            The date elements to use as defaults.
        :param ~typing.Any kwargs: Additional keywords passed to the filter.

        :returns: True if the file is to be kept, False otherwise.
    """

    def __call__(  # noqa: D102
        self, __date: datetime.date, default_date: DefaultDate = None, **kwargs
    ) -> bool: ...


FilterFunc = abc.Callable[["Finder", str, Matches], bool]
UserFuncGroupPartial = abc.Callable[[t.Any], bool]
UserFuncDatePartial = abc.Callable[[datetime.date], bool]


class Filter:
    """Manage a filter."""

    user_func: abc.Callable[..., bool]
    """Initial function given by the user."""
    partial_func: abc.Callable[..., bool]
    """Function with kwargs stored."""
    filter_func: FilterFunc
    """Function to be used as a filter."""
    name: str
    """Name of the filter."""

    def __init__(self, func: abc.Callable[..., bool], **kwargs):
        self.user_func = func
        self.partial_func = self.get_partial_func(**kwargs)
        self.filter_func = self.get_filter_func()
        self.name = self._get_name()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.name}>"

    def is_valid(self, finder: "Finder", filename: str, matches: Matches) -> bool:
        """Return if the corresponding filename is valid."""
        return self.filter_func(finder, filename, matches)

    def _get_name(self) -> str:
        return getattr(self.user_func, "__name__", "")

    def get_partial_func(self, **kwargs) -> abc.Callable[..., bool]:
        """Return user function with stored kwargs."""
        if kwargs:
            return functools.partial(self.user_func, **kwargs)
        return self.user_func

    def get_filter_func(self) -> FilterFunc:
        """Return filter function."""
        return self.partial_func


class FilterByGroup(Filter):
    """Manage a filter applied on specific groups.

    The list of indices of those groups must be supplied at initialization to avoid
    having to find them at each validation from a more generic key.
    """

    user_func: UserFuncGroup
    """Initial function given by the user."""
    partial_func: UserFuncGroupPartial
    """Function with kwargs stored."""
    indices: list[int]
    """List of group indices to apply this filter upon."""
    pass_unparsed: bool
    """Whether to pass unparsed groups to the filter."""
    filter_func: FilterFunc
    """Function to be used as a filter."""

    def __init__(
        self,
        user_func: abc.Callable[..., bool],
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
        name = f"{indices}:{name}"
        return name

    def get_filter_func(self) -> FilterFunc:
        """Return filter function.

        Wrap so the partial function is applied on every match specified by the
        :attr:`indices` and :attr:`pass_unparsed` attributes.
        """

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

    def reset(self) -> None:
        """Reset the filter function and name if the group indices have changed."""
        self.filter_func = self.get_filter_func()
        self.name = self._get_name()


class FilterByDate(Filter):
    """Manage a filter for the date.

    The user function will receive a date recovered from the matches.
    """

    user_func: UserFuncDate
    """Initial function given by the user."""
    partial_func: UserFuncDatePartial
    """Function with kwargs stored."""
    default_date: DefaultDate = None
    """Default date elements to use when recovering date."""

    def __init__(
        self,
        user_func: abc.Callable[..., bool],
        default_date: DefaultDate = None,
        **kwargs,
    ):
        self.default_date = default_date
        super().__init__(user_func, **kwargs)

    def get_filter_func(self) -> FilterFunc:
        """Return filter function.

        Wrap so the partial function is applied on a date recovered on matches, with the
        default elements from :attr:`default_date`.
        """

        def filt(finder: "Finder", filename: str, matches: Matches) -> bool:
            date = matches.get_date(default_date=self.default_date)
            return self.partial_func(date)

        return filt


class FilterList:
    """Container for filters.

    Has minimal interface: ``__getitem__``, ``__len__``, ``__iter__``, ``__contains__``
    """

    filters: list[Filter]
    """List of filters."""

    def __init__(self) -> None:
        self.filters = []

    def __getitem__(self, key: int) -> Filter:
        return self.filters[key]

    def __len__(self) -> int:
        return len(self.filters)

    def __iter__(self) -> abc.Iterator[Filter]:
        return iter(self.filters)

    def __contains__(self, x: t.Any) -> bool:
        return x in self.filters

    def __str__(self) -> str:
        return " ".join(map(str, self.filters))

    def is_valid(self, finder: "Finder", filename: str, matches: Matches) -> bool:
        """Return if the filename is valid.

        All filters are executed unless one rejects the filename.
        """
        return all(filt.is_valid(finder, filename, matches) for filt in self)

    def add(self, func: FilterFunc, **kwargs) -> Filter:
        """Add a basic filter."""
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
        """Add a group filter."""
        filt = FilterByGroup(func, indices, pass_unparsed=pass_unparsed)
        self.filters.append(filt)
        return filt

    def add_by_date(
        self,
        func: UserFuncDate,
        default_date: DefaultDate = None,
        **kwargs,
    ) -> FilterByDate:
        """Add a date filter."""
        filt = FilterByDate(func, default_date=default_date, **kwargs)
        self.filters.append(filt)
        return filt

    def clear(self):
        """Remove all filters."""
        self.filters.clear()

    def remove_by_group(self, indices: abc.Sequence[int]):
        """Remove groups from all filters.

        Every group filter indices has every index in the argument removed. Its match
        won't be sent to the filter anymore. If there is no index left, the filter is
        completely removed.
        """
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
        """Remove all date filters."""
        self.filters = [
            filt for filt in self.filters if not isinstance(filt, FilterByDate)
        ]
