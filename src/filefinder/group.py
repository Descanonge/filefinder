"""Group management."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import logging
import re
from typing import Any

from .format import Format

logger = logging.getLogger(__name__)


GroupKey = int | str
# Can be used to select one or more groups in a pattern.


class GroupParseError(Exception):
    """Custom errors when parsing group definition."""

    def __init__(self, definition, message):
        self.definition = definition
        self.message = message + f' ({definition})'


class Group:
    """Manage a group inside the filename pattern.

    Parameters
    ----------
    group:
        Group definition.
    idx:
        Index of the group in the filename pattern.

    Raises
    ------
    ValueError:
        Unable to parse the definition string into specifications.
    GroupParseError:
        Invalid definition.
    """

    _DEFAULT_GROUPS = {
        'I': [r'\d+', 'd'],
        'Y': [r'\d{4}', '04d'],
        'm': [r'\d\d', '02d'],
        'd': [r'\d\d', '02d'],
        'j': [r'\d{3}', '03d'],
        'H': [r'\d\d', '02d'],
        'M': [r'\d\d', '02d'],
        'S': [r'\d\d', '02d'],
        'x': [r'%Y%m%d', '08d'],
        'X': [r'%H%M%S', '06d'],
        'F': [r'%Y-%m-%d', 's'],
        'B': [r'[a-zA-Z]*', 's'],
        'text': [r'\w', 's'],
        'char': [r'\S*', 's']
    }
    """Regex str for each type of element."""

    _GROUP_REGEX = (
        r'(?P<name>\w*)'
        r'(:fmt=(?P<fmt>.*?))?'
        r'(?P<opt>:opt(?:=(?P<optA>.*?):(?P<optB>.*?))?)?'
        r'(:rgx=(?P<rgx>.*?))?'
        r'(?P<discard>:discard)?'
    )
    """Regex to find group properties from string definition."""

    def __init__(self, definition: str, idx: int):
        self.definition = definition
        """The string that created the group ``%(definition)``."""
        self.idx: int = idx
        """Index inside the pre-regex."""

        self.name: str
        """Group name."""
        self.rgx: str
        """Regex."""
        self.fmt: Format = Format('s')
        """Format string object."""
        self.discard: bool = False
        """If the group should not be used when retrieving values from matches."""
        self.opt: tuple[str] | bool = None
        """Optional keyword. If True, the whole group is optional. Else is a
        tuple of the two possibilities."""

        self.fixed_value: Any | None = None
        self.fixed_string: str | None = None

        self._parse_group_definition()

    def _parse_group_definition(self):
        """Parse group definition against a regex to retrieve specs."""
        m = re.fullmatch(self._GROUP_REGEX, self.definition)
        if m is None:
            raise ValueError(f'Unable to parse group definition ({self.definition})')

        self.name = m.group('name')
        self.discard = m.group('discard') is not None

        rgx = m.group('rgx')
        fmt = m.group('fmt')

        if self.name is None:
            raise GroupParseError(
                self.definition, 'No name was found in group definition.'
            )
        if rgx is not None and rgx == '':
            raise GroupParseError(
                self.definition,
                'Regex specification in group definition cannot be empty.'
            )
        if fmt is not None and fmt == '':
            raise GroupParseError(
                self.definition,
                'Format specification in group definition cannot be empty.'
            )

        # Set to defaults if name is known
        default = self._DEFAULT_GROUPS.get(self.name)
        if default is not None:
            self.rgx, fmt_def = default
            self.fmt = Format(fmt_def)

        # Override default format
        if fmt:
            self.fmt = Format(fmt)
            if not rgx:  # No need to generate rgx if it is provided
                self.rgx = self.fmt.generate_expression()

        if m.group('opt') is not None:
            opt_a, opt_b = m.group('optA'), m.group('optB')
            if opt_a is None and opt_b is None:
                self.opt = True
            else:
                opt_a = '' if opt_a is None else opt_a
                opt_b = '' if opt_b is None else opt_b
                self.opt = (opt_a, opt_b)
                self.rgx = f'{opt_a}|{opt_b}'

        # Override regex
        if rgx:
            self.rgx = rgx

        if self.rgx is None:
            raise GroupParseError(
                self.definition, 'No regex has been produced.')

    def __repr__(self):
        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self):
        return f'{self.name}:{self.idx:d}'

    def format(self, value: Any):
        """Return formatted string from value."""
        return self.fmt.format(value)

    def fix_value(self, fix: Any | bool | str):
        """Fix the group regex to a specific value.

        Parameters
        ----------
        fix:
            A string is directly used as a regular expression, otherwise the
            value is formatted according to the group 'format' specification.
        """
        self.fixed_value = fix

        # if optional A|B choice
        if isinstance(fix, bool) and isinstance(self.opt, tuple):
            fix = self.opt[fix]

        if not isinstance(fix, (list, tuple)):
            fix = [fix]

        fixes = [
            f if isinstance(f, str)  # if a string, leave it as is
            else re.escape(self.format(f))  # otherwise format it
            for f in fix
        ]
        self.fixed_string = '|'.join(fixes)

    def unfix(self):
        """Unfix value."""
        self.fixed_value = None
        self.fixed_string = None

    def get_regex(self) -> str:
        """Get group regex.

        Replace the matchers name by regex from `Matcher.NAME_RGX`. If there is
        a custom regex, recursively replace '%' followed by a single letter by
        the corresponding regex from `NAME_RGX`. '%%' is replaced by a single
        percentage character.

        Also applies 'optional' specification.

        Raises
        ------
        KeyError
            Unknown replacement.
        """
        def replace(match):
            group = match.group(1)
            if group == '%':
                return '%'
            if group in self._DEFAULT_GROUPS:
                replacement = self._DEFAULT_GROUPS[group][0]
                if '%' in replacement:
                    return self.get_regex(replacement)
                return replacement
            raise KeyError(f"Unknown replacement '{match.group(0)}'.")

        if self.fixed_string is not None:
            rgx = self.fixed_string
        else:
            rgx = re.sub('%([a-zA-Z%])', replace, self.rgx)

        # Make it matching
        rgx = f'({rgx})'

        if self.opt is True:
            rgx += '?'

        return rgx

def get_groups_indices(groups: list[Group],
                       key: GroupKey) -> list[int]:
    """Get list of groups indices corresponding to key.

    Key can be an integer index, or a string of the name, or a combination
    of the group and the name with the syntax 'group:name'

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
