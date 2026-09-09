"""Filters management."""

from __future__ import annotations

import functools
from collections.abc import Callable, Iterator, Sequence
from typing import TYPE_CHECKING, Any

from .matches import FileMatch

if TYPE_CHECKING:
    from .dates import DefaultDate
    from .finder import Finder


FilterFunc = Callable[["Finder", FileMatch], bool]


class Filter:
    """Manage a filter."""

    user_func: Callable[..., bool]
    """Initial function given by the user."""
    partial_func: Callable[..., bool]
    """Function with kwargs stored."""
    filter_func: FilterFunc
    """Function to be used as a filter."""
    name: str
    """Name of the filter."""

    def __init__(self, func: Callable[..., bool], **kwargs: Any) -> None:
        self.user_func = func
        self.partial_func = self.get_partial_func(**kwargs)
        self.filter_func = self.get_filter_func()
        self.name = self._get_name()

    def __str__(self) -> str:
        return f"<{self.__class__.__name__}:{self.name}>"

    def is_valid(self, finder: Finder, filematch: FileMatch) -> bool:
        """Return if the corresponding filename is valid."""
        return self.filter_func(finder, filematch)

    def _get_name(self) -> str:
        return getattr(self.user_func, "__name__", "")

    def get_partial_func(self, **kwargs: Any) -> Callable[..., bool]:
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

    user_func: Callable[..., bool]
    """Initial function given by the user."""
    partial_func: Callable[[Any], bool]
    """Function with kwargs stored."""
    indices: list[int]
    """List of group indices to apply this filter upon."""
    pass_unparsed: bool
    """Whether to pass unparsed groups to the filter."""
    filter_func: FilterFunc
    """Function to be used as a filter."""

    def __init__(
        self,
        user_func: Callable[..., bool],
        indices: Sequence[int],
        *,
        pass_unparsed: bool = False,
        **kwargs: Any,
    ) -> None:
        self.indices = list(indices)
        self.pass_unparsed = pass_unparsed
        super().__init__(user_func, **kwargs)

    def _get_name(self) -> str:
        name = super()._get_name()
        indices = ",".join(map(str, self.indices))
        return f"{indices}:{name}"

    def get_filter_func(self) -> FilterFunc:
        """Return filter function.

        Wrap so the partial function is applied on every match specified by the
        :attr:`indices` and :attr:`pass_unparsed` attributes.
        """

        def filt(finder: Finder, filematch: FileMatch) -> bool:  # noqa: ARG001
            values: list[Any] = []
            for i in self.indices:
                m = filematch.matches[i]
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

    date_name: str
    """Name of the corresponding pseudo-group."""
    user_func: Callable[..., bool]
    """Initial function given by the user."""
    partial_func: Callable[[Any], bool]
    """Function with kwargs stored."""
    default_date: DefaultDate
    """Default date elements to use when recovering date."""

    def __init__(
        self,
        user_func: Callable[..., bool],
        date_name: str,
        /,
        default_date: DefaultDate = None,
        **kwargs: Any,
    ) -> None:
        self.date_name = date_name
        self.default_date = default_date
        super().__init__(user_func, **kwargs)

    def get_filter_func(self) -> FilterFunc:
        """Return filter function.

        Wrap so the partial function is applied on a date recovered on matches, with the
        default elements from :attr:`default_date`.
        """

        def filt(finder: Finder, filematch: FileMatch) -> bool:  # noqa: ARG001
            date = filematch.get_value(self.date_name, default_date=self.default_date)
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

    def __iter__(self) -> Iterator[Filter]:
        return iter(self.filters)

    def __contains__(self, x: Any) -> bool:
        return x in self.filters

    def __str__(self) -> str:
        return " ".join(map(str, self.filters))

    def is_valid(self, finder: Finder, filematch: FileMatch) -> bool:
        """Return if the filename is valid.

        All filters are executed unless one rejects the filename.
        """
        return all(filt.is_valid(finder, filematch) for filt in self)

    def add(self, func: FilterFunc, **kwargs: Any) -> Filter:
        """Add a basic filter."""
        filt = Filter(func, **kwargs)
        self.filters.append(filt)
        return filt

    def add_by_group(
        self,
        func: Callable[..., bool],
        indices: Sequence[int],
        *,
        pass_unparsed: bool = False,
        **kwargs: Any,
    ) -> FilterByGroup:
        """Add a group filter."""
        filt = FilterByGroup(func, indices, pass_unparsed=pass_unparsed, **kwargs)
        self.filters.append(filt)
        return filt

    def add_by_date(
        self,
        func: Callable[..., bool],
        date_name: str,
        default_date: DefaultDate = None,
        **kwargs: Any,
    ) -> FilterByDate:
        """Add a date filter."""
        filt = FilterByDate(func, date_name, default_date=default_date, **kwargs)
        self.filters.append(filt)
        return filt

    def clear(self) -> None:
        """Remove all filters."""
        self.filters.clear()

    def remove_by_group(self, indices: Sequence[int]) -> None:
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

    def remove_by_date(self, date_name: str) -> None:
        """Remove filters corresponding to a date pseudo-group."""
        self.filters = [
            filt
            for filt in self.filters
            if not isinstance(filt, FilterByDate) or filt.date_name != date_name
        ]
