"""Generate regex from string format, and parse strings.

Parameters of the format-string are retrieved.
See `Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__.

Thoses parameters are then used to generate a regular expression, or to parse
a string formed from the format.

Only 's', 'd', 'f', 'e' and 'E' formats types are supported.

The width of the format string is not respected when matching with a regular
expression.
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


class FormatError(Exception):
    """Error related to Format object."""


class FormatParsingError(FormatError):
    """Could not parse a format-string."""


class DangerousFormatError(FormatError):
    """Dangerous format-string leading to ambiguities."""


class InvalidFormatTypeError(FormatError):
    """Unsupported type of format-string."""


class FormatValueParsingError(FormatError):
    """Could not parse value."""


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
            raise InvalidFormatTypeError(
                f"Invalid format type '{type}', expected one of {self.ALLOWED_TYPES}."
            )

    def format(self, value: Any) -> str:
        """Return formatted string of a value."""
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

    def generate_expression(self, capture=False) -> str:
        """Generate a regular expression matching strings created with this format.

        Parameters
        ----------
        capture
            If true, add capturing groups that will be used to parse the value by
            selecting only relevant information. Default is false.
        """
        raise NotImplementedError()


class FormatString(FormatAbstract):
    """Represent a format string for strings (type s)."""

    ALLOWED_TYPES = "s"

    type = "s"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if self.align == "=":
            raise FormatError("'=' alignement not allowed for string format.")
        if self.alternate:
            raise FormatError("Alternate form (#) not allowed for string format.")
        if self.grouping:
            raise FormatError("Grouping not allowed for string format.")
        if self.sign:
            raise FormatError("Sign not allowed for string format.")

    def parse(self, s: str) -> str:
        """Parse string generated with this format into an appropriate value."""
        pattern = self.generate_expression(capture=True)
        m = re.fullmatch(pattern, s)
        if m is None:
            raise FormatValueParsingError(
                f"Error parsing '{s}' with pattern '{pattern}'"
            )
        return m.group(1)

    def generate_expression(self, capture=False) -> str:
        """Generate a regular expression matching strings created with this format."""
        rgx = ".*?"
        if capture:
            rgx = f"({rgx})"
        rgx = self.add_outer_alignement(rgx)
        return rgx


class FormatNumberAbstract(FormatAbstract):
    """Represent a format string for numbers (type d, f, e, E)."""

    ALLOWED_TYPES = "dfeE"

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # Reject dubious formats
        digits = list(map(str, range(10)))
        if self.width > 0 and (
            (self.fill in digits and self.align in "<^")
            or (self.fill in digits[1:] and self.align in "=")
            or (self.fill in digits and self.align == ">" and self.sign == "-")
            or (self.fill == "-" and self.align in ">^=" and self.sign == "-")
        ):
            raise DangerousFormatError(
                f"Dangerous combination of fill character ({self.fill}), "
                f"alignement ({self.align}) and sign ({self.sign}) for "
                f"format ({self.fmt})"
            )

    def prepare_parse(self, s: str) -> str:
        """Remove special characters.

        Remove characters that throw off int() and float() parsing: fill/alignment
        characters and grouping symbols.

        Returns
        -------
        s
            a string ready to be casted to the appropriate type.
        """
        pattern = self.generate_expression(capture=True)
        m = re.fullmatch(pattern, s)
        if m is None:
            raise FormatValueParsingError(
                f"Error parsing '{s}' with pattern '{pattern}'"
            )
        # join all capturing groups (sign, number)
        s = "".join(m.groups(""))
        # remove grouping characters
        s = re.sub("[,_]", "", s)
        return s

    def get_left_of_decimal(self) -> str:
        """Get regex for the numbers left of decimal point.

        Will deal with grouping if present.
        """
        if self.grouping:
            rgx = rf"\d?\d?\d(?:{self.grouping}\d{{3}})*"
        else:
            rgx = r"\d+"
        return rgx

    def get_sign_regex(self, capture=False) -> str:
        """Get sign regex with approprite zero padding."""
        if self.sign == "-":
            rgx = "-?"
        elif self.sign == "+":
            rgx = r"[+-]"
        elif self.sign == " ":
            rgx = r"[\s-]"
        else:
            raise KeyError("Sign not in {+- }") from FormatError

        if capture:
            rgx = f"({rgx})"

        # padding is added between sign and numbers
        if self.width > 0 and self.align == "=":
            rgx = rgx + self.get_fill_regex()
        return rgx


class FormatInteger(FormatNumberAbstract):
    """Represent a format string for integers (type d)."""

    ALLOWED_TYPES = "d"

    def parse(self, s: str) -> int:
        """Parse string generated with format."""
        s = self.prepare_parse(s)
        return int(s)

    def generate_expression(self, capture=False) -> str:
        """Generate regex from format string."""
        rgx = self.get_sign_regex(capture=capture)
        number = self.get_left_of_decimal()
        if capture:
            number = f"({number})"
        rgx += number
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
        """Parse string generated with format."""
        s = self.prepare_parse(s)
        return float(s)

    def get_left_of_decimal(self) -> str:
        """Get regex for the numbers left of decimal point.

        Will deal with grouping if present. Some simplifications for eE formats.
        Only use groupings for '0=' alignment and enforce single digits grouping.
        """
        if self.type == "f":
            return super().get_left_of_decimal()
        if self.grouping and self.fill == "0" and self.align == "=":
            return rf"0?0?\d(?:{self.grouping}00\d)*"
        return r"\d"

    def generate_expression(self, capture=False) -> str:
        """Generate a regular expression matching strings created with this format."""
        if self.type == "f":
            rgx = self.get_sign_regex(capture=capture)
            number = self.get_left_of_decimal() + self.get_right_of_decimal()
            if capture:
                number = f"({number})"
            rgx += number

            rgx = self.add_outer_alignement(rgx)
            return rgx

        assert self.type in "eE"
        rgx = self.get_sign_regex(capture=capture)
        number = (
            self.get_left_of_decimal()
            + self.get_right_of_decimal()
            + rf"{self.type}[+-]\d{{2,3}}"
        )
        if capture:
            number = f"({number})"
        rgx += number
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
        raise FormatParsingError(f"Format-string '{format}' not valid.")
    params = m.groupdict()

    kind = params["type"]

    # fill boolean parameters
    params["alternate"] = params["alternate"] == "#"
    params["zero"] = params["zero"] == "0"

    # special case
    if params["zero"] and kind in "dfeE":
        if params["fill"] is None:
            params["fill"] = "0"
        if params["align"] is None:
            params["align"] = "="

    # TODO Precision not supported in s kind (it truncates the value)
    if kind == "s" and params["precision"]:
        raise FormatError("Precision parameter is currently not supported.")

    # defaults values for unset remaining parameters
    defaults = dict(align="<", fill=" ")
    if kind in "dfeE":
        defaults |= dict(align=">", sign="-", width="0", precision=".6", grouping="")

    for k, v in defaults.items():
        if params[k] is None:
            params[k] = v

    if kind in "dfeE":
        # convert to correct kind
        params["width"] = int(params["width"])
        params["precision"] = int(params["precision"].removeprefix("."))

    if kind not in FORMAT_CLASSES:
        raise InvalidFormatTypeError(
            f"Invalid format kind '{kind}', "
            f"expected one of '{list(FORMAT_CLASSES.keys())}'."
        )
    return FORMAT_CLASSES[kind](format, params)


# Retrocompatible alias
Format = get_format
