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
    """Parse a format string.

    Out of found parameters:
    - generate regular expression
    - format value
    - parse string into value

    Parameters
    ----------
    fmt: str
        Format string.
    """

    ALLOWED_TYPES = "sdfeE"

    def __init__(self, fmt: str, params: dict[str, Any]):
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

    def insert_alignement(self, rgx: str) -> str:
        """Add necessary regex for alignement characters.

        If width is not specified, does nothing.
        """
        if self.width == 0:
            return rgx

        if self.align == '=':
            raise ValueError("'=' align not supported for 's' format.")

        # Fill: the fill character any number of time, greedy
        fill_rgx = f"{re.escape(self.fill)}*"

        out_rgx = ""

        # value is right-aligned or center
        if self.align in ">^":
            out_rgx += fill_rgx

        out_rgx += rgx

        # value is left-aligned or center
        if self.align in "<^":
            out_rgx += fill_rgx

        return out_rgx


    def generate_expression(self) -> str:
        """Generate a regular expression matching strings created with this format.

        Will match any character, non-greedily.
        """
        rgx = ".*?"
        rgx = self.insert_alignement(rgx)
        return rgx


class FormatNumber(FormatAbstract):
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
        """Get regex for numbers left of decimal point."""
        if self.grouping:
            rgx = rf"\d?\d?\d(?:{self.grouping}\d{{3}})*"
        else:
            rgx = r"\d+"
        return rgx

    def get_sign(self) -> str:
        """Get sign regex."""
        if self.sign == "-":
            rgx = "-?"
        elif self.sign == "+":
            rgx = r"[+-]"
        elif self.sign == " ":
            rgx = r"[\s-]"
        else:
            raise KeyError("Sign not in {+- }")
        return rgx

    def insert_alignement(self, rgx: str) -> str:
        fill_rgx = ""
        if self.width > 0:
            fill_rgx += f"{re.escape(self.fill)}*"
        out_rgx = ""

        if self.align in ">^":
            out_rgx += fill_rgx

        out_rgx += self.get_sign()

        if self.align == "=":
            out_rgx += fill_rgx

        out_rgx += rgx

        if self.align in "<^":
            out_rgx += fill_rgx

        return out_rgx


class FormatInteger(FormatNumber):
    ALLOWED_TYPES = "d"

    def parse(self, s: str) -> int:
        s = self.remove_special(s)
        return int(s)

    def generate_expression(self) -> str:
        """Generate regex from format string."""
        rgx = self.get_left_of_decimal()
        rgx = self.insert_alignement(rgx)
        return rgx


class FormatFloat(FormatNumber):
    ALLOWED_TYPES = "feE"

    def get_right_of_decimal(self) -> str:
        rgx = ""
        if self.precision != 0 or self.alternate:
            rgx += r"\."
        if self.precision != 0:
            rgx += rf"\d{{{self.precision:d}}}"
        return rgx

    def parse(self, s: str) -> float:
        """Parse string generated with format.

        This simply use int() and float() to parse strings. Those are thrown
        off when using fill characters (other than 0), or thousands groupings,
        so we remove these from the string.

        Parsing will fail when using the '-' fill character on a negative
        number, or when padding with numbers. If you use such formats, please
        contact me to explain me why in the hell you do.
        """
        # Remove special characters (fill or groupings)
        s = self.remove_special(s)
        return float(s)

    def generate_expression(self) -> str:
        if self.type == "f":
            rgx = self.get_left_of_decimal()
            rgx += self.get_right_of_decimal()
            rgx = self.insert_alignement(rgx)
            return rgx

        assert self.type in "eE"
        rgx = r"\d"
        rgx += self.get_right_of_decimal()
        rgx += rf"{self.type}[+-]\d+"
        rgx = self.insert_alignement(rgx)
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
        align=">", fill=" ", sign="-", width="0", precision=".6", grouping=''
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
