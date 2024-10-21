"""Matches management."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import datetime
import logging
import re
import typing as t
from collections import abc

from .group import Group, GroupKey
from .util import Sentinel, get_groups_indices

logger = logging.getLogger(__name__)


PARSE_FAIL = Sentinel("Could not parse")
"""The match string could not be parsed successfully."""
NOT_PARSED = Sentinel("Not yet parsed")
"""The match string has not been parsed yet."""

DefaultDate = datetime.datetime | abc.Mapping[str, int] | None


class Match:
    """Match extract from a filename."""

    @classmethod
    def from_match(cls, group: Group, match: re.Match, idx: int) -> "Match":
        """Return Match object from a re.Match object.

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

    def __init__(self, group: Group, match_str: str, start: int, end: int):
        self.group: Group = group
        """Group used to get this match."""
        self.match_str: str = match_str
        """String matched in the filename."""
        self.start: int = start
        """Start index of match in the filename."""
        self.end: int = end
        """End index of match in the filename."""
        self._parsed: t.Any | Sentinel = NOT_PARSED

    def __repr__(self):
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self):
        """Human readable information."""
        return f"{self.group!s} = {self.match_str}"

    @property
    def match_parsed(self) -> t.Any | Sentinel:
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

    def get_match(self, parse: bool = True, raise_on_unparsed: bool = True) -> t.Any:
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


class Matches:
    """Scan an input file and store the results.

    Parameters
    ----------
    match
        Match object obtained from a filename. It should have as much capturing groups
        as the pattern.
    groups
        Sequence of Groups objects present in the pattern.

    """

    @classmethod
    def from_filename(
        cls, filename: str, pattern: re.Pattern | str, groups: abc.Sequence[Group]
    ) -> "Matches | None":
        """Find matches for a given filename.

        Parameters
        ----------
        filename:
            Filename to retrieve matches from.
        pattern
            Compiled match pattern to use. If left to None, we generate the current
            regex.

        Returns
        -------
        matches
            A :class:`Matches` object, or None if the filename did not match.

        Raises
        ------
        IndexError
            Not as many matches as groups. Maybe one of the group regex contains an
            additional (unwanted) capturing group ?
        """
        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        m = pattern.fullmatch(filename)
        if m is None:
            return None

        if len(groups) != len(m.groups()):
            raise IndexError(
                "Not as many captured matches as pattern groups. "
                "Does one of the group regex contains a capturing group ?"
            )

        matches = [Match.from_match(grp, m, i) for i, grp in enumerate(groups)]

        return cls(matches, groups)

    def __init__(self, matches: abc.Sequence[Match], groups: abc.Sequence[Group]):
        assert len(matches) == len(groups)

        self.matches: list[Match] = list(matches)
        """Matches for a single filename."""
        self.groups: list[Group] = list(groups)
        """Groups used."""

        self.date_is_first_class: bool = True

    def __repr__(self) -> str:
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self) -> str:
        """Human readable information."""
        return "\n".join([str(m) for m in self.matches])

    def __getitem__(self, key: GroupKey) -> t.Any:
        """Get first parsed value corresponding to key.

        Ignore groups with the 'discard' option.
        """
        return self.get_value(key, parse=True, keep_discard=False)

    def __iter__(self) -> abc.Iterator[Match]:
        """Iterate over matches."""
        return iter(self.matches)

    def __len__(self) -> int:
        """Return number of matches."""
        return len(self.matches)

    def get_values(
        self, key: GroupKey, parse: bool = True, keep_discard: bool = False
    ) -> list[t.Any]:
        """Get matched values corresponding to key.

        Return a list of values, even if only one group is selected.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.
        parse:
            If True (default), return the parsed value. If False return the
            matched string.
        keep_discard:
            If true groups with the 'discard' option are kept. Defauult is false.
        """
        matches = self.get_matches(key, keep_discard=keep_discard)
        values = [m.get_match(parse=parse) for m in matches]
        return values

    def get_value(
        self, key: GroupKey, parse: bool = True, keep_discard: bool = False
    ) -> t.Any:
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
        keep_discard:
            If true groups with the 'discard' option are kept. Defauult is false.

        Raises
        ------
        KeyError: No group with no 'discard' option was found.
        """
        values = self.get_values(key, parse=parse, keep_discard=keep_discard)
        if len(values) == 0:
            raise KeyError(
                "No group was found " f"(key: {key}, keep_discard: {keep_discard})"
            )
        if len(values) > 1:
            if any(v != values[0] for v in values[1:]):
                logger.warning(
                    "Different parsed values for key %s (%s)", str(key), repr(values)
                )
        return values[0]

    def get_matches(self, key: GroupKey, keep_discard: bool = False) -> list[Match]:
        """Get Match objects corresponding to key.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.
        keep_discard:
            If true groups with the 'discard' option are kept. Defauult is false.

        Returns
        -------
        List of Match corresponding to the key.
        """
        selected = get_groups_indices(self.groups, key, self.date_is_first_class)
        matches = [self.matches[k] for k in selected]
        if not keep_discard:
            matches = [m for m in matches if not m.group.discard]
        return matches

    def get_date(self, default_date: DefaultDate = None) -> datetime.datetime:
        """Retrieve date from matched elements.

        Matches that can be used are : YBmdjHMSFxX. If a matcher is *not* found in the
        filename, it will be replaced by the element of the default date argument. All
        values deduced from these matches will be compared. If different matchers give
        different values (for instance the group Y and F give a different year), an
        exception will be raised.

        Parameters
        ----------
        default_date:
            Default date. Datetime, or a mapping with keys in: year, month, day, hour,
            minute, and second. Defaults to 1970-01-01 00:00:00
        """
        from filefinder.library import get_date

        if isinstance(default_date, datetime.datetime):
            default_date = {
                attr: getattr(default_date, attr)
                for attr in ["year", "month", "day", "hour", "minute", "second"]
            }
        return get_date(self, default_date)
