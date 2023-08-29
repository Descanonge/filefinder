"""Matches management."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import logging
import re

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
        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self):
        return str(self.group) + f' = {self.match_str}'

    def get_match(self, parsed: bool = True):
        """Get match string or value.

        If `parsed` is true, and the parsing was successful, return the
        parsed value instead of the matched string.
        """
        if parsed:
            if self.match_parsed is None:
                raise ValueError(f"Failed to parse value '{self.match_str}' "
                                 f"for group '{self.group!s}'.")
            return self.match_parsed
        return self.match_str


class Matches:
    """Store multiples matches.

    Attributes
    ----------
    matches: list of :class:`Match`
        Matches for a single filename.
    groups: list of :class:`Group`
        Groups used.

    Raises
    ------
    ValueError
        Filename did not match pattern.
    IndexError
        Not as many matches as groups.
    """

    def __init__(self, groups: list[Group], filename: str,
                 pattern: re.Pattern):
        self.matches = []
        self.groups = groups

        m = pattern.fullmatch(filename)
        if m is None:
            raise ValueError('Filename did not match pattern.')
        if len(m.groups()) != len(groups):
            raise IndexError('Not as many matches as groups.')

        for i in range(len(groups)):
            self.matches.append(Match(groups[i], m, i))

    def __repr__(self):
        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self):
        return '\n'.join([str(m) for m in self.matches])

    def __getitem__(self, key: GroupKey):
        return self.get_matches(key)

    def __iter__(self):
        return iter(self.matches)

    def __len__(self):
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
