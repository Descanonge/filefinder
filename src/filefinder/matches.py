"""Matches management."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import logging
import re
import typing as t
from collections import abc

from .group import Group, GroupKey

logger = logging.getLogger(__name__)


class Match:
    """Match extract from a filename.

    Parameters
    ----------
    group
        Group used to get this match.
    match
        Match object for the complete filename.
    idx
        Index of the group in the match object.

    Attributes
    ----------
    group:
        Group used to get this match.
    match_str:
        String matched in the filename.
    start:
        Start index of match in the filename.
    end:
        End index of match in the filename.
    match_parsed:
        Parsed value. None if parsing was not successful.
    """

    def __init__(self, group: Group, match: re.Match, idx: int):
        self.group: Group = group
        self.match_str: str = match.group(idx + 1)
        self.start: int = match.start(idx + 1)
        self.end: int = match.end(idx + 1)

        self.match_parsed: t.Any = None
        try:
            self.match_parsed = group.parse(self.match_str)
        except Exception:
            logger.warning("Failed to parse for group %s", str(group))

    def __repr__(self):
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self):
        """Human readable information."""
        return f"{self.group!s} = {self.match_str}"

    def get_match(self, parse: bool = True) -> str | t.Any:
        """Get match string or value.

        Parameters
        ----------
        parse:
            If True (default), and the parsing was successful, return the
            parsed value instead of the matched string.

        Raises
        ------
        ValueError:
            Could not parse the match.
        """
        if parse:
            if self.match_parsed is None:
                raise ValueError(
                    f"Failed to parse value '{self.match_str}' "
                    f"for group '{self.group!s}'."
                )
            return self.match_parsed
        return self.match_str


class Matches:
    """Scan an input file and store the results.

    Parameter
    ---------
    groups:
        Groups present in the pattern.
    filename:
        Input filename to test.
    pattern:
        Regex to test, compiled.


    Raises
    ------
    ValueError
        Filename did not match pattern.
    IndexError
        Not as many matches as groups.
    """

    def __init__(self, groups: list[Group], filename: str, pattern: re.Pattern):
        self.matches: list[Match] = []
        """Matches for a single filename."""
        self.groups = groups
        """Groups used."""

        m = pattern.fullmatch(filename)
        if m is None:
            raise ValueError("Filename did not match pattern.")
        assert len(m.groups()) == len(groups), "Not as many matches as groups."

        for i in range(len(groups)):
            self.matches.append(Match(groups[i], m, i))

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
        return self.get_value(key, parse=True, discard=True)

    def __iter__(self) -> abc.Iterator[Match]:
        """Iterate over matches."""
        return iter(self.matches)

    def __len__(self) -> int:
        """Return number of matches."""
        return len(self.matches)

    def get_values(
        self, key: GroupKey, parse: bool = True, discard: bool = True
    ) -> list[str | t.Any]:
        """Get matched values corresponding to key.

        Return a list of values, even if only one group is selected.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.
        parse:
            If True (default), return the parsed value. If False return the
            matched string.
        discard:
            If True (default), groups with the 'discard' option are not kept.
        """
        matches = self.get_matches(key, discard)
        values = [m.get_match(parse=parse) for m in matches]
        return values

    def get_value(
        self, key: GroupKey, parse: bool = True, discard: bool = True
    ) -> str | t.Any:
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
        discard:
            If True (default), groups with the 'discard' option are not kept.

        Raises
        ------
        KeyError:
            No group with no 'discard' option was found.
        """
        values = self.get_values(key, parse, discard)
        if len(values) == 0:
            raise KeyError(
                "No group without a 'discard' option was found " f"(key: {key})"
            )
        if len(values) > 1:
            if any(v != values[0] for v in values[1:]):
                logger.warning(
                    "Different parsed values for key %s (%s)", str(key), repr(values)
                )
        return values[0]

    def get_matches(self, key: GroupKey, discard: bool = True) -> list[Match]:
        """Get matches corresponding to key.

        Parameters
        ----------
        key:
            Group(s) to select, either by index or name.
        discard:
            If True (default), groups with the 'discard' option are not kept.

        Returns
        -------
        List of Match corresponding to the key.
        """
        selected = get_groups_indices(self.groups, key)
        matches = [self.matches[k] for k in selected]
        if discard:
            matches = [m for m in matches if not m.group.discard]
        return matches


def get_groups_indices(groups: list[Group], key: GroupKey) -> list[int]:
    """Get sorted list of groups indices corresponding to key.

    Key can be an integer index, or a string of a group name. Since multiple
    groups can share the same name, multiple indices can be returned (sorted).

    Raises
    ------
    IndexError
        No group found corresponding to the key
    TypeError
        Key is not int or str
    """
    if isinstance(key, int):
        return [key]
    if isinstance(key, str):
        selected = [i for i, group in enumerate(groups) if group.name == key]

        if len(selected) == 0:
            raise IndexError(f"No group found for key '{key}'")
        return selected

    raise TypeError("Key must be int or str.")
