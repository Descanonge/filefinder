"""Group management."""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Sequence
from typing import Any, ClassVar, Self

from .dates import datetime_to_value
from .format import Format, FormatAbstract

logger = logging.getLogger(__name__)


GroupKey = int | str
"""Can be used to select one or more groups in a pattern."""


class GroupParseError(Exception):
    """Custom errors when parsing group definition."""


class GroupSpecs:
    """Parse and validate definition."""

    KEYVALS: ClassVar[list[str]] = ["fmt", "rgx", "pre", "post", "bool"]
    FLAGS: ClassVar[list[str]] = ["opt"]
    DEF_PATTERN: ClassVar[re.Pattern] = re.compile(
        "(?P<name>[^:]+)(?:"
        "(?P<fmt>:fmt.+?)"
        "|(?P<rgx>:rgx=.*?)"
        "|(?P<bool>:bool=.+?(?::.*?)??)"
        "|(?P<pre>:pre=.+?)"
        "|(?P<post>:post=.+?)"
        "|(?P<opt>:opt)"
        "){,6}"
    )

    def __init__(
        self,
        name: str,
        *,
        fmt: str | None,
        bool: dict[bool, str] | None = None,  # noqa: A002
        rgx: str | None,
        pre: str | None = None,
        post: str | None = None,
        opt: bool = False,
    ) -> None:
        self.name = name
        self.fmt = fmt
        self.bool = bool
        self.rgx = rgx
        self.pre = pre
        self.post = post
        self.opt = opt

        self.validate()

    def __str__(self) -> str:
        return str(self.as_dict(include_none=False))

    @classmethod
    def from_string(cls, definition: str) -> Self:
        """Parse group definition to retrieve name and specs."""
        m = cls.DEF_PATTERN.fullmatch(definition)
        if m is None:
            raise GroupParseError(
                f"Could not parse the group definition '{definition}'."
            )
        specs = m.groupdict()

        # Groups in the regex only store the last match found, to check for duplicates
        # we see if current specs account for the whole definition string
        if len(definition) != len(
            "".join([s for s in specs.values() if s is not None])
        ):
            raise GroupParseError(
                f"Duplicate spec detected in group definition '{definition}'"
            )

        for key in cls.KEYVALS:
            if (value := specs.get(key)) is not None:
                specs[key] = value.removeprefix(f":{key}=")
        for key in cls.FLAGS:
            specs[key] = specs[key] is not None

        if specs["bool"] is not None:
            options = specs["bool"].split(":", maxsplit=1)
            specs["bool"] = {
                True: options[0],
                False: options[1] if len(options) > 1 else "",
            }

        return cls(**specs)  # type: ignore[arg-type]

    def validate(self) -> None:
        """Validate specs."""
        if not self.name:
            raise GroupParseError("Group name cannot be empty.")

        if self.fmt is not None and not self.fmt:
            raise GroupParseError("Format string cannot be empty.")

        if self.bool is not None:
            self.bool.setdefault(False, "")
            if set(self.bool.keys()) != {False, True}:
                raise GroupParseError(
                    "Invalid bool spec mapping, it should contain boolean keys, with "
                    f"at least True defined ({self.bool})."
                )

    def as_dict(self, *, include_none: bool = True) -> dict[str, Any]:
        """Return dictionary containing specs."""
        out = {}
        for attr in ["name", "fmt", "bool", "rgx", "pre", "post", "opt"]:
            value = getattr(self, attr)
            if include_none or value is not None:
                out[attr] = value
        return out


class Group:
    """Manage a group inside the filename pattern.

    Parameters
    ----------
    definition:
        Group definition.
    idx:
        Index of the group in the filename pattern.
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
        self.options: dict[bool, str] | None = None
        """Dict of the two boolean possibilities."""
        self.optional: bool = False
        """Group is optional."""

        self.prefix: str = ""
        """Group prefix. Added to fixes and regex."""
        self.suffix: str = ""
        """Group suffix. Added to fixes and regex."""

        self.date_name: str | None = None
        self.date_element: str | None = None

        self._fixed = False
        self.fixed_value: Any | list[Any] | None = None
        self.fixed_string: str | list[str] | None = None  # to create filenames
        self.fixed_regex: str | None = None

        specs = GroupSpecs.from_string(definition)
        logger.debug("Parsed group definition %s to specs %s.", definition, specs)
        self._apply_specs(specs)

    def _apply_specs(self, specs: GroupSpecs) -> None:
        if "__" in specs.name:
            parts = specs.name.split("__")
            if len(parts) != 2 or not parts[0]:
                raise GroupParseError(
                    f"Invalid group name '{specs.name}'. "
                    "Use format '<date name>__<date element>'.",
                    self,
                )
            self.date_name, self.date_element = parts
            if self.date_element not in self.DATE_GROUPS:
                raise GroupParseError(
                    f"'{self.date_element}' is not a registered date element.", self
                )
        elif specs.name in self.DATE_GROUPS:
            self.date_name = "date"
            self.date_element = specs.name

        self.name = specs.name

        if self.date_element is not None:
            self.rgx, fmt_def = self.DATE_GROUPS[self.date_element]
            self.fmt = Format(fmt_def)

        if specs.pre is not None:
            self.prefix = specs.pre
        if specs.post is not None:
            self.suffix = specs.post
        self.optional = specs.opt

        # Override default format
        if specs.fmt:
            self.fmt = Format(specs.fmt)
            if not specs.rgx:  # No need to generate rgx if it is provided
                self.rgx = self.fmt.get_regex()

        # Boolean format
        if specs.bool is not None:
            self.options = specs.bool
            self.rgx = "|".join(re.escape(s) for s in specs.bool.values())

        # Override regex
        if specs.rgx:
            self.rgx = specs.rgx

        if not self.rgx:
            raise GroupParseError(
                "No regex has been produced. Group definition is missing properties "
                f"({self.definition})."
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
            for k, v in self.options.items():
                if string == v:
                    return k
            raise ValueError(
                f"Cannot parse '{string}' into boolean from options {self.options}"
            )

        return self.fmt.parse(string)

    def get_single_fix_result(self, fix: Any) -> tuple[Any, str, str]:
        """Return the fixed value, fixed string, and regex for a single fix.

        Parameters
        ----------
        fix:
            String or value to fix.

        Returns
        -------
        fixed_value: Any
            The fixed value. If the input fix is a date, the appropriate element is
            isolated.
        fixed_string: str
            The formatted fix, to use in filename creation.
        fixed_regex: str
            The resulting regex, to use in creating the Finder regex.
        """
        # if a string, leave it as is
        if isinstance(fix, str):
            return fix, fix, fix

        # None for optional group
        if fix is None and self.optional:
            return fix, "", ""

        # date, select correct element
        if isinstance(fix, dt.date | dt.datetime):
            if self.date_element is None:
                raise RuntimeError(
                    "Cannot fix a date object to a group not corresponding to a "
                    f"date element ({self})."
                )
            fixed_value = datetime_to_value(fix, self.date_element)
            fixed_string = self.prefix + self.fmt.format(fixed_value) + self.suffix
            return fixed_value, fixed_string, re.escape(fixed_string)

        # bool for A|B choice
        if isinstance(fix, bool):
            if self.options is None:
                raise ValueError(
                    f"{self.name} group has no A|B options, cannot fix with a boolean."
                )
            fixed_string = self.prefix + self.options[fix] + self.suffix
            return fix, fixed_string, re.escape(fixed_string)

        # otherwise, assume number
        fixed_string = self.prefix + self.format(fix) + self.suffix
        return fix, fixed_string, re.escape(fixed_string)

    def get_fix_result(
        self, fix: Any | Sequence[Any]
    ) -> tuple[Any, str, str] | tuple[list[Any], list[str], str]:
        """Return the fixed value, fixed string, and regex for one or more fix.

        Parameters
        ----------
        fix:
            String or value to fix, or a sequence thereof.

        Returns
        -------
        fixed_value:
            The fixed value(s). If the input fix is a date, this contains only the
            appropriate element.
        fixed_string:
            The formatted fix(es), to use in filename creation.
        fixed_regex:
            The regex, to use in creating the Finder regex. If there are multiple fix
            values, the regex is an OR pattern (without parentheses).
        """
        is_solo = isinstance(fix, str) or not isinstance(fix, Sequence)
        if is_solo:
            fix = [fix]

        if len(fix) == 0:
            raise ValueError("A list of fixes must contain at least one element.")

        results = [self.get_single_fix_result(f) for f in fix]
        values, strings, regexes = [list(i) for i in zip(*results, strict=True)]

        if is_solo:
            return values[0], strings[0], regexes[0]
        return values, strings, "|".join(regexes)

    def fix(self, fix: Any | Sequence[Any]) -> None:
        """Fix the group regex to a specific value.

        Parameters
        ----------
        fix:
            A string is directly used as a regular expression, otherwise the
            value is formatted according to the group specifications.
        """
        values, strings, regex = self.get_fix_result(fix)

        self._fixed = True
        self.fixed_value = values
        self.fixed_string = strings
        self.fixed_regex = regex

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

        if self.optional and not self.fixed:
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
