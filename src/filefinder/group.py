"""Group management."""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Sequence
from typing import Any, ClassVar, Self

from .date_elements import DateElement
from .format import Format, FormatAbstract

logger = logging.getLogger(__name__)


GroupKey = int | str
"""Type to use to select one or more groups in a pattern."""


class GroupParseError(Exception):
    """Custom errors when parsing group definition."""


class GroupSpecs:
    """Parse and validate definition."""

    KEYVALS: ClassVar[list[str]] = ["fmt", "rgx", "pre", "post", "bool"]
    """Specs in the group definition that correspond to key-values."""
    FLAGS: ClassVar[list[str]] = ["opt"]
    """Specs in the group definition that correspond to flags."""
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
    """Regex pattern to find definition specs."""

    def __init__(
        self,
        name: str,
        *,
        definition: str = "",
        fmt: str | None = None,
        bool: dict[bool, str] | None = None,  # noqa: A002
        rgx: str | None = None,
        pre: str | None = None,
        post: str | None = None,
        opt: bool = False,
    ) -> None:
        self.definition = definition
        self.name = name
        self.fmt = fmt
        self.bool = bool
        self.rgx = rgx
        self.pre = pre
        self.post = post
        self.opt = opt

        self.date_name: str | None = None
        self.date_element: DateElement | None = None
        self.name_to_date_element()

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
                f"Duplicate spec detected in group definition '{definition}'."
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

        specs_obj = cls(**specs, definition=definition)  # type: ignore[arg-type]
        logger.debug("Parsed group definition %s to specs %s.", definition, specs_obj)
        return specs_obj

    def name_to_date_element(self) -> None:
        """Find date name and date element from group name.

        Set attributes from either a name of the form `<date_name>__<date_element>` or
        if the name is a registered date element.
        """
        if "__" in self.name:
            parts = self.name.split("__")
            if len(parts) != 2 or not parts[0]:
                raise GroupParseError(
                    f"Invalid group name '{self.name}'. "
                    f"Use format '<date name>__<date element>' ({self.definition}).",
                )
            self.date_name, date_element = parts
            if date_element not in DateElement.registered():
                raise GroupParseError(
                    f"'{self.date_element}' is not a registered date element "
                    f"({self.definition})."
                )
            self.date_element = DateElement.get(date_element)
        elif self.name in DateElement.registered():
            self.date_name = "date"
            self.date_element = DateElement.get(self.name)

    def create_group(self) -> Group:
        """Create corresponding group object.

        Disptach to correct Group subclass.
        """
        if not self.name:
            raise GroupParseError(f"Group name cannot be empty ({self.definition}).")

        if self.fmt is not None and not self.fmt:
            raise GroupParseError(f"Format string cannot be empty ({self.definition}).")

        if self.date_element is not None:
            return DateGroup.from_specs(self)

        if self.bool is not None:
            self.bool.setdefault(False, "")
            if set(self.bool.keys()) != {False, True}:
                raise GroupParseError(
                    "Invalid bool spec mapping, it should contain boolean keys, with "
                    f"at least True defined ({self.bool}, {self.definition}).",
                )
            return BoolGroup.from_specs(self)

        return Group.from_specs(self)

    def as_dict(self, *, include_none: bool = True) -> dict[str, Any]:
        """Return dictionary containing specs."""
        out = {}
        for attr in [
            "name",
            "fmt",
            "bool",
            "rgx",
            "pre",
            "post",
            "opt",
            "date_element",
        ]:
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
    """

    definition: str
    """The string that created the group ``%(definition)``."""

    name: str
    """Group name."""
    rgx: str
    """Regex."""
    fmt: FormatAbstract
    """Format string object."""
    optional: bool
    """Group is optional."""

    prefix: str
    """Group prefix. Added to fixes and regex."""
    suffix: str
    """Group suffix. Added to fixes and regex."""

    fixed_value: Any | list[Any] | None
    """Current fixed value(s). None if not fixed."""
    fixed_string: str | list[str] | None
    """String representation(s) of current fixed value(s). None if not fixed."""
    fixed_regex: str | None
    """Regex to match current fixed value(s). None if not fixed."""

    def __init__(
        self,
        name: str,
        *,
        rgx: str | None = None,
        fmt: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
        optional: bool = False,
        definition: str = "",
    ) -> None:
        self.definition = definition
        self.name = name
        self.optional = optional

        self._fixed = False
        self.fixed_value = None
        self.fixed_string = None
        self.fixed_regex = None

        self.prefix = prefix if prefix is not None else ""
        self.suffix = suffix if suffix is not None else ""

        self.rgx = ""
        self.fmt = Format("s")

        if fmt:
            self.fmt = Format(fmt)
            if not rgx:  # No need to generate rgx if it is provided
                self.rgx = self.fmt.get_regex()

        # Override regex
        if rgx:
            self.rgx = rgx

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
        return self.name

    @classmethod
    def from_specs(cls, specs: GroupSpecs) -> Self:
        """Create Group object from specs object. Check conflicts."""
        return cls(
            specs.name,
            rgx=specs.rgx,
            fmt=specs.fmt,
            prefix=specs.pre,
            suffix=specs.post,
            optional=specs.opt,
            definition=specs.definition,
        )

    @classmethod
    def from_string(cls, definition: str) -> Group:
        """Create Group object (or subclass) from string definition."""
        return GroupSpecs.from_string(definition).create_group()

    @property
    def fixed(self) -> bool:
        """True if the group has fixed value(s)."""
        return self._fixed

    def format(self, value: Any) -> str:
        """Return formatted string from value."""
        return self.fmt.format(value)

    def parse(self, string: str) -> Any:
        """Parse value from string."""
        if self.prefix:
            string = string.removeprefix(self.prefix)
        if self.suffix:
            string = string.removesuffix(self.suffix)

        return self.fmt.parse(string)

    def get_single_fix_result(self, fix: Any) -> tuple[Any, str, str]:
        """Return the fixed value, fixed string, and regex for a single fix.

        Parameters
        ----------
        fix:
            String or value to fix:

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
            return (
                fix,
                self.prefix + fix + self.suffix,
                re.escape(self.prefix) + fix + re.escape(self.suffix),
            )

        # None for optional group
        if fix is None and self.optional:
            return fix, "", ""

        if isinstance(fix, dt.date | dt.datetime):
            raise RuntimeError(
                "Cannot fix a date object to a group not corresponding to a "
                f"date element ({self})."
            )
        if isinstance(fix, bool):
            raise ValueError(
                f"{self.name} group has no A|B options, cannot fix with a boolean."
            )

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
            rgx = re.escape(self.prefix) + rgx + re.escape(self.suffix)

        if self.optional and not self.fixed:
            rgx = f"(?:{rgx})?"
            # Note we don't use "({rgx})?", because if missing from the filename we
            # couldn't retrieve the start and end indices of the group.
            # (m.start(i) would return -1)

        # Make it matching
        rgx = f"({rgx})"

        return rgx


class BoolGroup(Group):
    """Group selecting between two strings.

    Syntax is ``bool:<true>[:<false>]``. False option may be omitted if empty.
    The format ``fmt`` cannot be user-specified.

    Parameters
    ----------
    options:
        The two strings
        Dictionary of boolean to string.
    """

    def __init__(
        self,
        name: str,
        *,
        definition: str = "",
        options: dict[bool, str],
        rgx: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
        optional: bool = False,
    ) -> None:
        self.options: dict[bool, str] = options
        """Dict of the two boolean possibilities."""

        if not rgx:
            rgx = "|".join(re.escape(s) for s in options.values())

        super().__init__(
            name=name,
            rgx=rgx,
            prefix=prefix,
            suffix=suffix,
            optional=optional,
            definition=definition,
        )

    @classmethod
    def from_specs(cls, specs: GroupSpecs) -> Self:
        """Create Group object from specs object. Check conflicts."""
        for attr in ("fmt", "enum"):
            if getattr(specs, attr) is not None:
                raise GroupParseError(
                    f"Cannot specify `{attr}` for a bool group ({specs.definition})."
                )

        if specs.bool is None:
            raise GroupParseError(
                f"`bool` cannot be None for a boolean group ({specs.definition})"
            )

        return cls(
            specs.name,
            options=specs.bool,
            rgx=specs.rgx,
            prefix=specs.pre,
            suffix=specs.post,
            optional=specs.opt,
            definition=specs.definition,
        )

    def get_single_fix_result(self, fix: Any) -> tuple[Any, str, str]:
        """Return the fixed value, fixed string, and regex for a single fix.

        Fix can be a boolean, selecting one of the two options.
        """
        if isinstance(fix, bool):
            fixed_string = self.prefix + self.options[fix] + self.suffix
            return fix, fixed_string, re.escape(fixed_string)
        return super().get_single_fix_result(fix)

    def parse(self, string: str) -> Any:
        """Parse value from string."""
        if self.prefix:
            string = string.removeprefix(self.prefix)
        if self.suffix:
            string = string.removesuffix(self.suffix)

        for k, v in self.options.items():
            if string == v:
                return k
        raise ValueError(
            f"Cannot parse '{string}' into boolean from options {self.options}"
        )


class EnumGroup(Group):
    """Group whose value must be from a fixed set.

    Syntax is ``enum:<A>:<B>:...``.
    The format ``fmt`` cannot be specified.
    """

    def __init__(
        self,
        name: str,
        *,
        definition: str = "",
        enum: set[str],
        rgx: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
        optional: bool = False,
    ) -> None:
        self.enum: set[str] = enum

        if not rgx:
            rgx = "|".join(re.escape(s) for s in enum)

        super().__init__(
            name,
            rgx=rgx,
            fmt="s",
            prefix=prefix,
            suffix=suffix,
            optional=optional,
            definition=definition,
        )


class DateGroup(Group):
    """Group corresponding to a date element.

    Specific syntax is all in the name, either:
    - name of the form ``<date_name>__<date_element>``,
    - a registered date element.

    See :doc:`handling_dates`.

    As for other groups, if a format ``fmt`` is given it will be used to generate a
    regex, unless a regex ``rgx`` is given. Otherwise, the corresponding
    :class:`.DateElement` object will dictate the default format and regex.

    Parameters
    ----------
    date_name:
        Date groups with the same date name can be managed as a date pseudo-group.
    date_element:
        Object indicating what element the group corresponds to.

    """

    def __init__(
        self,
        name: str,
        *,
        definition: str = "",
        date_name: str,
        date_element: DateElement,
        rgx: str | None = None,
        fmt: str | None = None,
        prefix: str | None = None,
        suffix: str | None = None,
        optional: bool = False,
    ) -> None:
        self.date_name: str = date_name
        """Name of the parent date pseudo-group. None if not a date group."""
        self.date_element: DateElement = date_element
        """Name of the date element (Y, m, d, ...). None if not a date group."""

        if not rgx:
            rgx = Format(fmt).get_regex() if fmt else self.date_element.regex
        if not fmt:
            fmt = self.date_element.fmt

        super().__init__(
            name,
            rgx=rgx,
            fmt=fmt,
            prefix=prefix,
            suffix=suffix,
            optional=optional,
            definition=definition,
        )

    @classmethod
    def from_specs(cls, specs: GroupSpecs) -> Self:
        """Create Group object from specs object. Check conflicts."""
        for attr in ("enum", "bool"):
            if getattr(specs, attr) is not None:
                raise GroupParseError(
                    f"Cannot specify `{attr}` for a date group ({specs.definition})."
                )

        if not specs.date_name:
            raise GroupParseError(f"Date name cannot be empty ({specs.definition}).")
        if specs.date_element is None:
            raise GroupParseError(f"Date element cannot be None ({specs.definition}).")

        return cls(
            specs.name,
            date_name=specs.date_name,
            date_element=specs.date_element,
            rgx=specs.rgx,
            fmt=specs.fmt,
            prefix=specs.pre,
            suffix=specs.post,
            optional=specs.opt,
            definition=specs.definition,
        )

    def get_single_fix_result(self, fix: Any) -> tuple[Any, str, str]:
        """Return the fixed value, fixed string, and regex for a single fix.

        Fix can be a :mod:`datetime` object from which the correct value will be
        extracted.
        """
        if isinstance(fix, dt.date | dt.datetime):
            fixed_value = self.date_element.datetime_to_value(fix)
            fixed_string = self.prefix + self.fmt.format(fixed_value) + self.suffix
            return fixed_value, fixed_string, re.escape(fixed_string)

        return super().get_single_fix_result(fix)


def get_groups_indices(groups: list[Group], key: GroupKey) -> list[int]:
    """Get sorted list of groups indices corresponding to key.

    Key can be an integer index, or a string of a group name. Since multiple
    groups can share the same name, multiple indices can be returned (sorted).

    Raises
    ------
    IndexError
        No group corresponding to the key
    TypeError
        Key is not int or str
    """
    if isinstance(key, int):
        if key < 0 or key >= len(groups):
            raise IndexError(f"Group index {key} out of range ({len(groups)} groups)")
        return [key]
    if isinstance(key, str):
        selected = [
            i
            for i, group in enumerate(groups)
            if key == group.name
            or (isinstance(group, DateGroup) and key == group.date_name)
        ]

        if len(selected) == 0:
            raise IndexError(f"No group found for key '{key}'")
        return selected

    raise TypeError("Key must be int or str.")


def get_date_names(groups: Sequence[Group]) -> set[str]:
    """Get the names of date pseudo-groups."""
    return {g.date_name for g in groups if isinstance(g, DateGroup)}
