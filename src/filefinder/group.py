"""Group management."""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Sequence
from typing import Any, ClassVar

from .dates import datetime_keys, datetime_to_value
from .format import Format, FormatAbstract

logger = logging.getLogger(__name__)


GroupKey = int | str
"""Can be used to select one or more groups in a pattern."""

"""On Group parsing:

explain reasoning behind PATTERN, and alternatives explored
"""


class GroupParseError(Exception):
    """Custom errors when parsing group definition."""

    def __init__(self, message: str, group: Group | None = None) -> None:
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
    GroupParseError
        Invalid group definition.
    """

    PATTERN: ClassVar[re.Pattern] = re.compile(
        f"(?P<name>[^:]+?(?::[{datetime_keys}])?)(?:"
        "(?P<fmt>:fmt=.+?)"
        "|(?P<rgx>:rgx=.*?)"
        "|(?P<bool>:bool=.*?(?::.*?)??)"
        "|(?P<opt>:opt)"
        "|(?P<pre>:pre=.*?)"
        "|(?P<post>:post=.*?)"
        "){,6}"
    )
    """Pattern used to find properties in group definition.

    See :meth:`_check_duplicates` for details on the pattern matching.
    """

    DATE_GROUPS: ClassVar[dict[str, tuple[str, str]]] = {
        "Y": (r"\d{4}", "04d"),  # year
        "m": (r"\d\d", "02d"),  # month
        "d": (r"\d\d", "02d"),  # day
        "j": (r"\d{3}", "03d"),  # dayofyear
        "H": (r"\d\d", "02d"),  # hour
        "M": (r"\d\d", "02d"),  # minute
        "S": (r"\d\d", "02d"),  # second
        "x": (r"\d{8}", "08d"),  # date
        "X": (r"\d{6}", "06d"),  # time
        "F": (r"\d{4}-\d\d-\d\d", "s"),  # formated date
        "B": (r"\w+", "s"),  # month / month abbreviation
    }
    """Regex and format strings for various default groups.

    See the :ref:`name` section of documentation for details.
    """

    def __init__(self, definition: str, idx: int) -> None:
        self.definition = definition
        """The string that created the group ``%(definition)``."""
        self.idx: int = idx
        """Index inside the pre-regex."""

        self.name: str = ""
        """Group name."""
        self.rgx: str = ""
        """Regex."""
        self.fmt: FormatAbstract = Format("s")
        """Format string object."""
        self.options: tuple[str, str] | None = None
        """Tuple of the two possibilities indicated by the full ``:bool``
        specification, in order (False, True), so that a simple getitem works."""
        self.optional: bool = False
        """If True, the whole group is marked as optional (``()?``).
        Is set to False unless specification ':opt' is indicated."""

        self.prefix: str = ""
        """Group prefix. Added to fixes and regex."""
        self.suffix: str = ""
        """Group suffix. Added to fixes and regex."""

        self.date_name: str | None = None
        self.date_element: str | None = None
        self.is_date: bool = False
        self.name_date: tuple[str, str] | None = None

        self._fixed = False
        self.fixed_value: Any | list[Any] | None = None
        self.fixed_string: str | list[str] | None = None  # to create filenames
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

        if ":" in self.name:
            self.date_name, self.date_element = self.name.rsplit(":", 1)
            if self.date_element not in self.DATE_GROUPS:
                raise GroupParseError(
                    f"'{self.date_element}' is not a registered date element.", self
                )
        elif self.name in self.DATE_GROUPS:
            self.date_name = "date"
            self.date_element = self.name

        if self.date_element is not None:
            self.is_date = True
            self.rgx, fmt_def = self.DATE_GROUPS[self.date_element]
            self.fmt = Format(fmt_def)

        # Extract specs
        for k in ["rgx", "fmt", "bool", "pre", "post"]:
            if specs[k] is not None:
                specs[k] = specs[k].removeprefix(f":{k}=")
        rgx = specs["rgx"]
        fmt = specs["fmt"]
        bol = specs["bool"]

        if (prefix := specs["pre"]) is not None:
            self.prefix = prefix
        if (suffix := specs["post"]) is not None:
            self.suffix = suffix
        self.optional = specs["opt"] is not None

        # Override default format
        if fmt:
            self.fmt = Format(fmt)
            if not rgx:  # No need to generate rgx if it is provided
                self.rgx = self.fmt.generate_expression()

        # Boolean format
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
            raise GroupParseError(
                "No regex has been produced. Group definition is missing properties.",
                self,
            )

    def _check_duplicates(self, m: re.Match) -> None:
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
        if self.prefix:
            string = string.removeprefix(self.prefix)
        if self.suffix:
            string = string.removesuffix(self.suffix)

        # parsing boolean
        if self.options is not None:
            if string == self.options[0]:
                return False
            if string == self.options[1]:
                return True
            raise ValueError(
                f"Cannot parse '{string}' into boolean from options {self.options}"
            )

        return self.fmt.parse(string)

    def fix(self, fix: Any | Sequence[Any]) -> None:
        """Fix the group regex to a specific value.

        Parameters
        ----------
        fix:
            A string is directly used as a regular expression, otherwise the
            value is formatted according to the group 'format' specification.
        """
        is_solo = isinstance(fix, str) or not isinstance(fix, Sequence)
        if is_solo:
            fix = [fix]

        if len(fix) == 0:
            raise ValueError("A list of fixes must contain at least one element.")

        strings = []
        regexes = []
        values = []
        for f in fix:
            val: Any = f

            # if a string, leave it as is
            if isinstance(f, str):
                out = f
                rgx = f

            # date
            elif isinstance(f, dt.date | dt.datetime):
                if self.date_element is None:
                    raise RuntimeError(
                        "Cannot fix a date object to a group not corresponding to a "
                        f"date element ({self})."
                    )
                val = datetime_to_value(f, self.date_element)
                out = self.prefix + self.fmt.format(val) + self.suffix
                rgx = re.escape(out)

            # if optional A|B choice
            elif isinstance(f, bool):
                if self.options is None:
                    raise ValueError(
                        f"{self.name} group has no A|B options, "
                        "cannot fix value with a boolean."
                    )
                out = self.prefix + self.options[f] + self.suffix
                rgx = re.escape(out)

            else:
                # otherwise, assume number
                out = self.prefix + self.format(f) + self.suffix
                rgx = re.escape(out)
            values.append(val)
            strings.append(out)
            regexes.append(rgx)

        self._fixed = True
        self.fixed_value = values[0] if is_solo else values
        self.fixed_string = strings[0] if is_solo else strings
        self.fixed_regex = "|".join(regexes)

    def unfix(self) -> None:
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
            rgx = self.prefix + rgx + self.suffix

        if self.optional is True:
            rgx = f"(?:{rgx})?"

        # Make it matching
        rgx = f"({rgx})"

        return rgx


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
        selected = [
            i for i, group in enumerate(groups) if key in {group.name, group.date_name}
        ]

        if len(selected) == 0:
            raise IndexError(f"No group found for key '{key}'")
        return selected

    raise TypeError("Key must be int or str.")


def get_date_names(groups: Sequence[Group]) -> set[str]:
    """Get the names of date pseudo-groups."""
    return {g.date_name for g in groups if g.date_name is not None}
