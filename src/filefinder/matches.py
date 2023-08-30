"""Matches management."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import logging
import re
from collections.abc import Iterator
from typing import Any

from .group import Group, GroupKey, get_groups_indices

logger = logging.getLogger(__name__)


class Match:
    """Match extract from a filename.

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
        self.group = group
        self.match_str = match.group(idx+1)
        self.start = match.start(idx+1)
        self.end = match.end(idx+1)

        self.match_parsed = None
        try:
            self.match_parsed = group.fmt.parse(self.match_str)
        except Exception:
            logger.warning('Failed to parse for group %s', str(group))

    def __repr__(self):
        """Human readable information."""
        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self):
        """Human readable information."""
        return str(self.group) + f' = {self.match_str}'

    def get_match(self, parsed: bool = True) -> str | Any:
        """Get match string or value.

        If `parsed` is true, and the parsing was successful, return the
        parsed value instead of the matched string.

        Raises
        ------
        ValueError:
            Could not parse the match. Could
        """
        if parsed:
            if self.match_parsed is None:
                raise ValueError(f"Failed to parse value '{self.match_str}' "
                                 f"for group '{self.group!s}'.")
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

    def __init__(self, groups: list[Group],
                 filename: str,
                 pattern: re.Pattern):
        self.matches: list[Match] = []
        """Matches for a single filename."""
        self.groups = groups
        """Groups used."""

        m = pattern.fullmatch(filename)
        if m is None:
            raise ValueError('Filename did not match pattern.')
        if len(m.groups()) != len(groups):
            raise IndexError('Not as many matches as groups.')

        for i in range(len(groups)):
            self.matches.append(Match(groups[i], m, i))

    def __repr__(self) -> str:
        """Human readable information."""
        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self) -> str:
        """Human readable information."""
        return '\n'.join([str(m) for m in self.matches])

    def __getitem__(self, key: GroupKey) -> Match | list[Match]:
        """Get matches corresponding to key."""
        return self.get_matches(key)

    def __iter__(self) -> Iterator[Match]:
        """Iterate over matches."""
        return iter(self.matches)

    def __len__(self) -> int:
        """Return number of matches."""
        return len(self.matches)

    def get_matches(self, key: GroupKey) -> Match | list[Match]:
        """Get matches corresponding to key.

        See :func:`Finder.get_groups
        <filefinder.finder.Finder.get_groups>` for details on
        `key` argument.
        :func:`__getitem__` wraps around this method.

        Returns
        -------
        List of Match corresponding to the key. If only one Match corresponds,
        return it directly.
        """
        selected = get_groups_indices(self.groups, key)
        matches = [self.matches[k] for k in selected]
        if len(matches) == 1:
            return matches[0]
        return matches


def get_groups_indices(groups: list[Group],
                       key: GroupKey) -> list[int]:
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
        selected = [i for i, group in enumerate(groups)
                    if group.name == key]

        if len(selected) == 0:
            raise IndexError(f"No group found for key '{key}'")
        return selected

    raise TypeError('Key must be int or str.')
