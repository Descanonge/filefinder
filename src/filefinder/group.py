"""Group management."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

from __future__ import annotations

import logging
import re
from typing import Any

from .format import FormatAbstract, get_format

logger = logging.getLogger(__name__)


GroupKey = int | str
"""Can be used to select one or more groups in a pattern."""

"""On Group parsing:

explain reasoning behind PATTERN, and alternatives explored
"""


class GroupParseError(Exception):
    """Custom errors when parsing group definition."""

    def __init__(self, message: str, group: Group | None = None):
        if group is not None:
            message += f" ({group.definition})"
        super().__init__(message)


class Group:
    """Manage a group inside the filename pattern.

    Parameters
    ----------
    definition:
        Group definition.
    idx:
        Index of the group in the filename pattern.

    Raises
    ------
    GroupParseError: Invalid group definition.
    """

    PATTERN = re.compile(
        "(?P<name>[^:]+?)(?:(?P<fmt>:fmt=.+?)|(?P<rgx>:rgx=.*?)"
        "|(?P<bool>:bool=.*?(?::.*?)??)"
        "|(?P<opt>:opt)|(?P<discard>:discard)){,5}"
    )
    """Pattern used to find properties in group definition.

    See :meth:`_check_duplicate` for details on the pattern matching.
    """

    DEFAULT_GROUPS = {
        "I": [r"\d+", "d"],  # index
        "Y": [r"\d{4}", "04d"],  # year
        "m": [r"\d\d", "02d"],  # month
        "d": [r"\d\d", "02d"],  # day
        "j": [r"\d{3}", "03d"],  # dayofyear
        "H": [r"\d\d", "02d"],  # hour
        "M": [r"\d\d", "02d"],  # minute
        "S": [r"\d\d", "02d"],  # second
        "x": [r"%Y%m%d", "08d"],  # date
        "X": [r"%H%M%S", "06d"],  # time
        "F": [r"%Y-%m-%d", "s"],  # formated date
        "B": [r"[a-zA-Z]*", "s"],  # month / month abbreviation
        "text": [r"\w", "s"],
        "char": [r"\S*", "s"],
    }
    """Regex and format strings for various default groups.

    See the :ref:`name` section of documentation for details.
    """

    def __init__(self, definition: str, idx: int):
        self.definition = definition
        """The string that created the group ``%(definition)``."""
        self.idx: int = idx
        """Index inside the pre-regex."""

        self.name: str = ""
        """Group name."""
        self.rgx: str = ""
        """Regex."""
        self.fmt: FormatAbstract = get_format("s")
        """Format string object."""
        self.discard: bool = False
        """If the group should not be used when retrieving values from matches."""
        self.options: tuple[str, str] | None = None
        """Tuple of the two possibilities indicated by the full ``:bool``
        specification, in order (False, True), so that a simple getitem works."""
        self.optional: bool = False
        """If True, the whole group is marked as optional (``()?``).
        Is set to False unless specification ':opt' is indicated."""

        self._fixed = False
        self.fixed_value: Any | None = None
        self.fixed_string: str | None = None
        self.fixed_regex: str | None = None

        self._parse_group_definition()

    def _parse_group_definition(self) -> None:
        """Parse group definition against a regex to retrieve specs.

        See :meth:`_check_duplicate` for details on the pattern matching.
        """
        m = self.PATTERN.fullmatch(self.definition)
        if m is None:
            raise GroupParseError("Could not parse the group definition.", self)
        self._check_duplicates(m)
        specs = m.groupdict()

        self.name = specs["name"]

        # Set to defaults if name is known
        default = self.DEFAULT_GROUPS.get(self.name)
        if default is not None:
            self.rgx, fmt_def = default
            self.fmt = get_format(fmt_def)

        # Extract specs
        for k in ["rgx", "fmt", "bool"]:
            if specs[k] is not None:
                specs[k] = specs[k].removeprefix(f":{k}=")
        rgx = specs["rgx"]
        fmt = specs["fmt"]
        bol = specs["bool"]

        # Flags
        self.discard = specs["discard"] is not None
        self.optional = specs["opt"] is not None

        # Override default format
        if fmt:
            self.fmt = get_format(fmt)
            if not rgx:  # No need to generate rgx if it is provided
                self.rgx = self.fmt.generate_expression()

        # Boolean format
        self.options = None
        if bol is not None:
            options = bol.split(":", maxsplit=1)
            if len(options) == 1:
                options.append("")
            self.options = tuple(options[::-1])
            self.rgx = "|".join(re.escape(s) for s in options)

        # Override regex
        if rgx:
            self.rgx = rgx

        if not self.rgx:
            raise GroupParseError("No regex has been produced.", self)

        if self.options is not None:
            # rgx is A|B, A and B being strings we don't do "% replacement"
            return
        self.rgx = self._replace_regex_defaults(self.rgx)

    def _check_duplicates(self, m: re.Match):
        """Check if the definition does not contain duplicates.

        The matching pattern (:attr:`PATTERN`) is written so that specs (rgx, fmt, ...)
        can be given in any order, while still matching the full string.

        The pattern is made of every possible spec in a OR list, which can be repeated
        up to 5 times. Regex only keep the last captured group. We must be a bit sly
        to check duplicates. For that I check that the groups we have account for
        the whole string. If part of the string is not in our match, something has
        been overwritten.
        """
        accounted_for: list[tuple[int, int]] = []

        for k, v in m.groupdict().items():
            if v is not None:
                accounted_for.append((m.start(k), m.end(k)))

        accounted_for.sort(key=lambda x: x[0])

        # to make sure we get to the end
        n = len(self.definition)
        accounted_for.append((n, n))

        pos = 0
        for span in accounted_for:
            if pos == span[0]:
                pos = span[1]
            else:
                raise GroupParseError(
                    (
                        "The specs found do not account for the full definition. "
                        "There is most likely a duplicate spec."
                    ),
                    self,
                )

    def _replace_regex_defaults(self, regex: str) -> str:
        """Recursively replace defaults regexes of the form ``%[a-zA-Z]``.

        Replacements are taken from :attr:`Group.DEFAULT_GROUPS`.

        A '%' in the regex should be escaped by another: '%%'.

        Raises
        ------
        KeyError: Unknown replacement.
        """

        def replace(match: re.Match):
            group = match.group(1)
            if group == "%":
                return "%"
            if group in self.DEFAULT_GROUPS:
                replacement = self.DEFAULT_GROUPS[group][0]
                if "%" in replacement:  # need to go recursive
                    return self._replace_regex_defaults(replacement)
                return replacement
            raise KeyError(f"Unknown replacement '{match.group(0)}'.")

        return re.sub("%([a-zA-Z%])", replace, regex)

    def __repr__(self) -> str:
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self) -> str:
        """Human readable information."""
        return f"{self.name}:{self.idx:d}"

    @property
    def fixed(self) -> bool:
        """True if the group has fixed value(s)."""
        return self._fixed

    def format(self, value: Any) -> str:
        """Return formatted string from value."""
        return self.fmt.format(value)

    def parse(self, string: str) -> Any:
        """Return parsed value from string."""
        # parsing boolean
        if self.options is not None:
            if string == self.options[0]:
                return False
            elif string == self.options[1]:
                return True
            else:
                raise ValueError(
                    f"Cannot parse '{string}' into boolean from options {self.options}"
                )

        return self.fmt.parse(string)

    def fix_value(self, fix: Any | bool | str):
        """Fix the group regex to a specific value.

        Parameters
        ----------
        fix:
            A string is directly used as a regular expression, otherwise the
            value is formatted according to the group 'format' specification.
        """
        self._fixed = True
        self.fixed_value = fix

        if not isinstance(fix, list | tuple):
            fix = [fix]

        if len(fix) == 0:
            raise ValueError("A list of fixes must contain at least one element.")

        strings = []
        regexes = []
        for f in fix:
            # if a string, leave it as is
            if isinstance(f, str):
                out = f
                rgx = f
            # if optional A|B choice
            elif isinstance(f, bool):
                if self.options is None:
                    raise ValueError(
                        f"{self.name} group has no A|B options, "
                        "cannot fix value with a boolean."
                    )
                out = self.options[f]
                rgx = re.escape(out)
            else:
                out = self.format(f)
                rgx = re.escape(out)
            strings.append(out)
            regexes.append(rgx)

        self.fixed_string = strings[0]
        self.fixed_regex = "|".join(regexes)

    def unfix(self):
        """Unfix value."""
        self._fixed = False
        self.fixed_value = None
        self.fixed_string = None
        self.fixed_regex = None

    def get_regex(self) -> str:
        """Get group regex.

        Returns the fixed value if previously specified.
        Insert the regex into a capturing group, and make it optional if
        the ``:opt`` was indicated
        """
        if self.fixed_regex is not None:
            rgx = self.fixed_regex
        else:
            rgx = self.rgx

        # Make it matching
        rgx = f"({rgx})"

        if self.optional is True:
            rgx += "?"

        return rgx
