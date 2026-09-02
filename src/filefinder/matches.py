"""Matches management."""

import datetime
import logging
import os.path
import re
import warnings
from collections.abc import Iterator, Sequence
from typing import Any, Self

from .dates import DefaultDate, get_date
from .group import Group, GroupKey, get_date_names, get_groups_indices

logger = logging.getLogger(__name__)


class Sentinel:
    """Sentinel objects."""

    def __init__(self, msg: str = "") -> None:
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


PARSE_FAIL = Sentinel("Could not parse")
"""The match string could not be parsed successfully."""
NOT_PARSED = Sentinel("Not yet parsed")
"""The match string has not been parsed yet."""


class GroupMatch:
    """Value extracted from a filename for a single group."""

    @classmethod
    def from_match(cls, group: Group, match: re.Match, idx: int) -> Self:
        """Return GroupMatch object from a re.Match object.

        Parameters
        ----------
        group
            Group used to get this match.
        match
            Match object for the complete filename.
        idx
            Index of the group in the match object.
        """
        match_str = match.group(idx + 1)
        start = match.start(idx + 1)
        end = match.end(idx + 1)
        return cls(group, match_str, start, end)

    def __init__(self, group: Group, match_str: str, start: int, end: int) -> None:
        self.group: Group = group
        """Group used to get this match."""
        self.match_str: str = match_str
        """String matched in the filename."""
        self.start: int = start
        """Start index of match in the filename."""
        self.end: int = end
        """End index of match in the filename."""
        self._parsed: Any | Sentinel = NOT_PARSED

    def __repr__(self) -> str:
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self) -> str:
        """Human readable information."""
        return f"{self.group!s} = {self.match_str}"

    @property
    def match_parsed(self) -> Any | Sentinel:
        """Return value or Sentinel value if failing to parse.

        Returns :attr:`PARSE_FAIL` if an exception is thrown when trying to parse the
        match.
        """
        if self._parsed is NOT_PARSED:
            try:
                self._parsed = self.group.parse(self.match_str)
            except Exception:
                self._parsed = PARSE_FAIL
                logger.debug("Failed to parse for group %s", str(self.group))
        return self._parsed

    def can_parse(self) -> bool:
        """Return if the match can be parsed."""
        return self.match_parsed is not PARSE_FAIL

    def get_match(self, *, parse: bool = True, raise_on_unparsed: bool = True) -> Any:
        """Get match string or value.

        Parameters
        ----------
        parse
            If True (default) return the parsed value instead of the matched string.
        raise_on_unparsed
            If True (default), will raise an error if the parsed value was asked but the
            parsing failed. If False, return the string match instead.

        Raises
        ------
        ValueError
            Could not parse the match.
        """
        if parse:
            if self.can_parse():
                return self.match_parsed

            if raise_on_unparsed:
                raise ValueError(
                    f"Failed to parse value '{self.match_str}' "
                    f"for group '{self.group!s}'."
                )
        return self.match_str


class FileMatch:
    """Scan an input file and store the results.

    Parameters
    ----------
    root
        Root directory containing files.
    filename
        Filename from which matches are extracted, relative to root directory.
    match
        Regex match object obtained from a filename. It should have as much capturing
        groups as the pattern.
    groups
        Sequence of Groups objects present in the pattern.
    """

    def __init__(
        self,
        root: str,
        filename: str,
        matches: Sequence[GroupMatch],
        groups: Sequence[Group],
    ) -> None:
        assert len(matches) == len(groups)

        self.root: str = root
        self.filename: str = filename
        self.matches: list[GroupMatch] = list(matches)
        """Matches for every group."""
        self.groups: list[Group] = list(groups)
        """Groups present in the pattern."""

    def __repr__(self) -> str:
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self) -> str:
        """Human readable information."""
        return "\n".join(
            [f"from filename: {self.filename}"] + [str(m) for m in self.matches]
        )

    def __getitem__(self, key: GroupKey) -> Any:
        """Get first parsed value corresponding to key."""
        return self.get_value(key, parse=True)

    def __iter__(self) -> Iterator[GroupMatch]:
        """Iterate over matches."""
        return iter(self.matches)

    def __len__(self) -> int:
        """Return number of matches."""
        return len(self.matches)

    def get_filename(self, *, relative: bool = True) -> str:
        """Get filename corresponding to matches.

        :param relative: If True (default), return relative to the finder root
            directory. If not, return as absolute path.
        """
        if relative:
            return self.filename
        return os.path.join(self.root, self.filename)

    def get_values(
        self,
        key: GroupKey,
        *,
        parse: bool = True,
        default_date: DefaultDate = None,
    ) -> list[Any]:
        """Get matched values corresponding to key.

        Return a list of values, even if only one group is selected.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.
        parse:
            If True (default), return the parsed value. If False return the
            matched string.
        default_date:
            If key correspond to a date pseudo-group, use this as the default date
            elements. Datetime, or a mapping with keys in: year, month, day, hour,
            minute, and second. Defaults to 1970-01-01 00:00:00
        """
        matches = self.get_matches(key)

        if key in get_date_names(self.groups):
            if isinstance(default_date, datetime.datetime):
                default_date = {
                    attr: getattr(default_date, attr)
                    for attr in ["year", "month", "day", "hour", "minute", "second"]
                }
            return [get_date(matches, default_date)]

        return [m.get_match(parse=parse) for m in matches]

    def get_value(
        self,
        key: GroupKey,
        *,
        parse: bool = True,
        default_date: DefaultDate = None,
    ) -> Any:
        """Get matched value corresponding to key.

        Return a single value. If multiple groups correspond to ``key``,
        the value of the first one to appear in the pattern is returned.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.
        parse:
            If True (default), return the parsed value. If False return the
            matched string.
        default_date:
            If key correspond to a date pseudo-group, use this as the default date
            elements. Datetime, or a mapping with keys in: year, month, day, hour,
            minute, and second. Defaults to 1970-01-01 00:00:00

        Raises
        ------
        KeyError
            No group with was found.
        """
        values = self.get_values(key, parse=parse, default_date=default_date)
        if len(values) == 0:
            raise KeyError(f"No group was found for key '{key}'")
        if len(values) > 1:
            if any(v != values[0] for v in values[1:]):
                logger.warning(
                    "Different parsed values for key %s (%s)", str(key), repr(values)
                )
        return values[0]

    def get_matches(self, key: GroupKey) -> list[GroupMatch]:
        """Get GroupMatch objects corresponding to key.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.

        Returns
        -------
        List of GroupMatch corresponding to the key.
        """
        selected = get_groups_indices(self.groups, key)
        return [self.matches[k] for k in selected]
