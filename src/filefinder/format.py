"""Generate regex from string format, and parse strings.

Parameters of the format-string are retrieved.
See `Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__.

Thoses parameters are then used to generate a regular expression, or to parse
a string formed from the format.

Only 's', 'd', 'f', 'e' and 'E' formats types are supported.

The width of the format string is not respected when matching with a regular
expression.

The parsing is quite naive and can fail on some cases.
See :func:`Format.parse` for details.

The regex generation and parsing are tested in `tests/unit/test_format.py`.
"""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import re
from collections.abc import Mapping
from typing import Any

FORMAT_REGEX = (
    r"((?P<fill>.)?(?P<align>[<>=^]))?"
    r"(?P<sign>[-+ ])?"
    r"(?P<z>z)?(?P<alternate>#)?(?P<zero>0)?"
    r"(?P<width>\d+?)?"
    r"(?P<grouping>[,_])?"
    r"(?P<precision>\.\d+?)?"
    r"(?P<type>[a-zA-Z])"
)
"""The regular expression used to parse a format string.

Follows the Format Specification Mini-Language.
``[[fill]align][sign]["z"]["#"]["0"][width][grouping_option]["." precision][type]``
"""
FORMAT_PATTERN = re.compile(FORMAT_REGEX)


class FormatAbstract:
    """Represent a format string.

    Can generate an appropriate regular expression corresponding to that format string
    (to some limitations), generate a string from a value, or parse such a string into
    a value.

    Users are not meant to instanciate those objects directly, use :func:`get_format`
    instead (or its alias for retro-compatibility :func:`Format`).

    Parameters
    ----------
    fmt:
        Format string.
    params:
        Mapping of options/parameters of the format mini-language to their values.
        (type, fill, align, sign, alternate, zero, width, grouping, precision).
        They should not contain None values.
    """

    ALLOWED_TYPES = "sdfeE"

    def __init__(self, fmt: str, params: Mapping[str, Any]):
        self.fmt: str = fmt

        self.type: str = params["type"]
        self.fill: str = params["fill"]
        self.align: str = params["align"]
        self.sign: str = params["sign"]
        self.alternate: bool = params["alternate"]
        self.zero: bool = params["zero"]
        self.width: int = params["width"]
        self.grouping: str = params["grouping"]
        self.precision: int = params["precision"]

        if self.type not in self.ALLOWED_TYPES:
            raise KeyError(
                f"Invalid format type '{type}', expected one of {self.ALLOWED_TYPES}."
            )

    def format(self, value: Any) -> str:
        """Return formatted string."""
        return f"{{:{self.fmt}}}".format(value)

    def get_fill_regex(self):
        """Return regex for matching fill characters."""
        return f"{re.escape(self.fill)}*"

    def add_outer_alignement(self, rgx: str) -> str:
        """Add necessary regex for alignement characters.

        If width is not specified, does nothing.
        """
        if self.width == 0 or self.align == "=":
            return rgx

        out = [rgx]
        fill_rgx = self.get_fill_regex()

        # value is right-aligned or center
        if self.align in ">^":
            out.insert(0, fill_rgx)

        # value is left-aligned or center
        if self.align in "<^":
            out.append(fill_rgx)

        return "".join(out)

    def parse(self, s: str) -> Any:
        """Parse string generated with this format into an appropriate value."""
        raise NotImplementedError()

    def generate_expression(self) -> str:
        """Generate a regular expression matching strings created with this format."""
        raise NotImplementedError()


class FormatString(FormatAbstract):
    """Represent a format string for strings (type s)."""

    ALLOWED_TYPES = "s"

    type = "s"

    def parse(self, s: str) -> str:
        """Parse string generated with this format into an appropriate value.

        Only return string here.
        """
        return s

    def generate_expression(self) -> str:
        """Generate a regular expression matching strings created with this format.

        Will match any character, non-greedily.
        """
        rgx = ".*?"
        rgx = self.add_outer_alignement(rgx)
        return rgx


class FormatNumberAbstract(FormatAbstract):
    """Represent a format string for numbers (type d, f, e, E)."""

    ALLOWED_TYPES = "dfeE"

    def remove_special(self, s: str) -> str:
        """Remove special characters.

        Remove characters that throw off int() and float() parsing.
        Namely fill and grouping characters.
        Will remove fill, except when fill is zero (parsing functions are
        okay with that).
        """
        to_remove = [",", "_"]  # Any grouping char
        if self.fill != "0":
            to_remove.append(re.escape(self.fill))
        pattern = "[{}]".format("".join(to_remove))
        return re.sub(pattern, "", s)

    def get_left_of_decimal(self) -> str:
        """Get regex for the numbers left of decimal point.

        Will deal with grouping if present.
        """
        if self.grouping:
            rgx = rf"\d?\d?\d(?:{self.grouping}\d{{3}})*"
        else:
            rgx = r"\d+"
        return rgx

    def get_sign_regex(self) -> str:
        """Get sign regex with approprite zero padding."""
        if self.sign == "-":
            rgx = "-?"
        elif self.sign == "+":
            rgx = r"[+-]"
        elif self.sign == " ":
            rgx = r"[\s-]"
        else:
            raise KeyError("Sign not in {+- }")

        # padding is added between sign and numbers
        if self.width > 0 and self.align == "=":
            rgx = rgx + self.get_fill_regex()
        return rgx


class FormatInteger(FormatNumberAbstract):
    """Represent a format string for integers (type d)."""

    ALLOWED_TYPES = "d"

    def parse(self, s: str) -> int:
        """Parse string generated with format.

        This simply use int() to parse strings. Those are thrown
        off when using fill characters (other than 0), or thousands groupings,
        so we remove these from the string.

        Parsing will fail for some deviously chaotic formats such as using the '-' fill
        character on a negative number, or when padding with numbers.
        """
        s = self.remove_special(s)
        return int(s)

    def generate_expression(self) -> str:
        """Generate regex from format string."""
        rgx = self.get_sign_regex() + self.get_left_of_decimal()
        rgx = self.add_outer_alignement(rgx)
        return rgx


class FormatFloat(FormatNumberAbstract):
    """Represent a format string for floats (type f, e, E)."""

    ALLOWED_TYPES = "feE"

    def get_right_of_decimal(self) -> str:
        """Return regex for numbers after decimal points.

        Including the decimal point itself. It will respect 'alternate' option and
        the specified precision.
        """
        rgx = ""
        if self.precision != 0 or self.alternate:
            rgx += r"\."
        if self.precision != 0:
            rgx += rf"\d{{{self.precision:d}}}"
        return rgx

    def parse(self, s: str) -> float:
        """Parse string generated with format.

        This simply use float() to parse strings. Those are thrown
        off when using fill characters (other than 0), or thousands groupings,
        so we remove these from the string.

        Parsing will fail for some deviously chaotic formats such as using the '-' fill
        character on a negative number, or when padding with numbers.
        """
        # Remove special characters (fill or groupings)
        s = self.remove_special(s)
        return float(s)

    def generate_expression(self) -> str:
        """Generate a regular expression matching strings created with this format."""
        if self.type == "f":
            rgx = (
                self.get_sign_regex()
                + self.get_left_of_decimal()
                + self.get_right_of_decimal()
            )
            rgx = self.add_outer_alignement(rgx)
            return rgx

        assert self.type in "eE"
        rgx = (
            self.get_sign_regex()
            + r"\d"
            + self.get_right_of_decimal()
            + rf"{self.type}[+-]\d+"
        )
        rgx = self.add_outer_alignement(rgx)
        return rgx


FORMAT_CLASSES: dict[str, type[FormatAbstract]] = dict(
    s=FormatString,
    d=FormatInteger,
    f=FormatFloat,
    e=FormatFloat,
    E=FormatFloat,
)


def get_format(format: str) -> FormatAbstract:
    """Parse format parameters and return appropriate Format object."""
    m = FORMAT_PATTERN.fullmatch(format)
    if m is None:
        raise ValueError("Format spec not valid.")
    params = m.groupdict()

    # fill boolean parameters
    params["alternate"] = params["alternate"] == "#"
    params["zero"] = params["zero"] == "0"

    # special case
    if params["align"] is None and params["zero"]:
        params["fill"] = "0"
        params["align"] = "="

    # defaults values for unset remaining parameters
    defaults = dict(
        align=">", fill=" ", sign="-", width="0", precision=".6", grouping=""
    )
    for k, v in defaults.items():
        if params[k] is None:
            params[k] = v

    # convert to correct type
    params["width"] = int(params["width"])
    params["precision"] = int(params["precision"].removeprefix("."))

    type = params["type"]
    if type not in FORMAT_CLASSES:
        raise KeyError(
            f"Invalid format type '{type}', "
            f"expected one of '{list(FORMAT_CLASSES.keys())}'."
        )
    return FORMAT_CLASSES[type](format, params)


# Retrocompatible alias
Format = get_format
