"""Date related utilities."""

from __future__ import annotations

import calendar
import datetime as dt
import re
import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | dt.date | Mapping[str, int]
"""Type for default_date argument."""

DATETIME_KEYS = "YBmdjHMSFxX"
TIME_KEYS = "XHMS"

DATETIME_ATTRIBUTES = {
    "F": ["year", "month", "day"],
    "x": ["year", "month", "day"],
    "Y": ["year"],
    "m": ["month"],
    "d": ["day"],
    "B": ["month"],
    "j": ["month", "day"],
    "X": ["hour", "minute", "second"],
    "H": ["hour"],
    "M": ["minute"],
    "S": ["second"],
}
"""Attributes of datetime objects for each group name."""

DATETIME_FORMAT = {
    "F": "{:04d}-{:02d}-{:02d}",
    "x": "{:04d}{:02d}{:02d}",
    "Y": "{:04d}",
    "m": "{:02d}",
    "d": "{:02d}",
    "B": "{:s}",
    "j": "{:03d}",
    "X": "{:02d}{:02d}{:02d}",
    "H": "{:02d}",
    "M": "{:02d}",
    "S": "{:02d}",
}
"""Format for each group name"""


def make_date_groups(date_format: str, name: str = "") -> str:
    """Create a pattern string for multiple dates groups.

    Parameters
    ----------
    date_format:
        A date format as given to strftime, with each group marked with a percent sign
        followed a default element ('%Y' for instance).
    name:
        Name of all the date groups. Can be left empty.

    Example
    -------
    >>> make_date_groups("%Y%m%d", name="start")
    "%(start__Y)%(start__m)%(start__d)"
    >>> make_date_groups("%Y-%m-%d %H:%M:%S")
    "%(Y)%(m)%(d) %(H):%(M):%(S)"
    """
    if name:
        name = f"{name}__"

    def replace(match: re.Match) -> str:
        group = match.group(1)
        if group == "%":
            return "%"
        if group in DATETIME_KEYS:
            return f"%({name}{group})"
        raise KeyError(f"Unknown datetime key '{match.group(0)}'.")

    return re.sub("%([a-zA-Z%])", replace, date_format)


def _check_input(date: dt.datetime | dt.date, name: str) -> None:
    if name in TIME_KEYS and not isinstance(date, dt.datetime):
        raise TypeError(
            f"'{name}' group needs time information (received a {type(date)} object)"
        )
    if name not in DATETIME_ATTRIBUTES:
        raise KeyError(f"'{name}' group name not registered in util.datetime_format")


def datetime_to_str(date: dt.datetime | dt.date, element: str) -> str:
    """Format a date element (Y, m, F, ...) from a datetime object."""
    _check_input(date, element)

    if element == "j":
        return f"{get_doy(date):03d}"
    if element == "B":
        return date.strftime("%B")

    elements = [getattr(date, attr) for attr in DATETIME_ATTRIBUTES[element]]
    fmt = DATETIME_FORMAT[element]
    return fmt.format(*elements)


def datetime_to_value(date: dt.datetime | dt.date, name: str) -> int | str:
    """Extract value of date element (Y, m, F, ...) from a datetime object."""
    _check_input(date, name)

    if name == "j":
        return get_doy(date)

    if name in "xXFB":
        s = datetime_to_str(date, name)
        # xX can be returned as int, as per their format in Group.DATE_GROUPS
        return int(s) if name in "xX" else s

    elements = [getattr(date, attr) for attr in DATETIME_ATTRIBUTES[name]]
    if len(elements) != 1:
        raise IndexError(f"Date element '{name}' returned multiple elements.")

    return elements[0]


def get_doy(date: dt.date | dt.datetime) -> int:
    """Return the dayofyear of a date."""
    if isinstance(date, dt.datetime):
        date = date.date()
    return (date - dt.date(date.year, 1, 1)).days + 1


def date_from_doy(doy: int, year: int) -> dict[str, int]:
    """Get month and day from a dayofyear value (and its year)."""
    day = dt.date(year, 1, 1) + dt.timedelta(days=doy - 1)
    return {"month": day.month, "day": day.day}


class DateParser:
    """Parse date from matches.

    Matches that can be used are in ``YBmdjHMSFxX``. If different matchers give
    different values for the same element (for instance the group Y and F give a
    different year), an exception will be raised.

    Parameters
    ----------
    matches:
        Matches obtained from a filename.
    default_date:
        If an element is not found in the filename, use the element from this default
        date. It can be a :mod:`datetime` object or a mapping with keys among: year,
        month, day, hour, minute, and second. Missing elements will default to
        1970-01-01 00:00:00
    """

    DEFAULT_DATE_DEFAULT: ClassVar[dict[str, int]] = {
        "year": 1970,
        "month": 1,
        "day": 1,
        "hour": 0,
        "minute": 0,
        "second": 0,
    }

    def __init__(
        self, matches: Sequence[GroupMatch], default_date: DefaultDate | None = None
    ) -> None:
        self.matches: list[GroupMatch] = list(matches)
        for m in self.matches:
            if m.group.date_element is None:
                raise TypeError(
                    f"Group '{m.group!s}' does not correspond to a date element."
                )

        if default_date is None:
            default_date = {}
        if isinstance(default_date, dt.datetime):
            default_date = {
                attr: getattr(default_date, attr)
                for attr in ["year", "month", "day", "hour", "minute", "second"]
            }
        elif isinstance(default_date, dt.date):
            default_date = {
                attr: getattr(default_date, attr) for attr in ["year", "month", "day"]
            }

        self.default_date = self.DEFAULT_DATE_DEFAULT | dict(default_date)
        self.elements: dict[str, list[int]] = {}

    @classmethod
    def parse(
        cls, matches: Sequence[GroupMatch], default_date: DefaultDate | None = None
    ) -> dt.datetime:
        """Retrieve a date from matches."""
        parser = cls(matches, default_date)
        return parser.retrieve_date()

    def retrieve_date(self) -> dt.datetime:
        """Retrieve a date from matches."""
        self.fill_elements()
        self.validate_elements()
        return self.create_date()

    def fill_elements(self) -> None:
        """Fill the elements attributes from values found in matches."""
        self.elements = {}

        self.process("B", self.process_B)
        self.process("F", self.process_F)
        self.process("x", self.process_x)
        self.process("X", self.process_X)

        for name in "YmdHMS":
            self.process(name, self.process_YmdHMS)

        # process j last, it needs month and year set
        self.process("j", self.process_j)

    def validate_elements(self) -> None:
        """Validate the elements.

        Warn if no element were found, raise if they are different values for the same
        element.
        """
        if len(self.elements) == 0:
            warnings.warn(
                "No date elements could be recovered. Returning default date.",
                stacklevel=1,
            )

        for elt, values in self.elements.items():
            if any(v != values[0] for v in values):
                raise ValueError(f"Different values found for {elt}: {values}")

    def create_date(self) -> dt.datetime:
        """Create a datetime object from found elements."""
        date = dict(self.default_date)
        for elt, values in self.elements.items():
            date[elt] = values[0]

        return dt.datetime(**date)  # type: ignore[arg-type]

    def process(
        self,
        date_element: str,
        callback: Callable[[GroupMatch], Mapping[str, int]],
    ) -> None:
        """Find values for a given date element.

        Callback is a bound method that takes the group match and return a dictionary
        of elements to values.
        """
        for m in self.matches:
            if m.group.date_element == date_element:
                for elt, val in callback(m).items():
                    if elt not in self.elements:
                        self.elements[elt] = []
                    self.elements[elt].append(val)

    def process_YmdHMS(self, m: GroupMatch) -> dict[str, int]:  # noqa: N802
        """Process match for YmdHMS elements."""
        value = m.get_match(parse=True)
        assert m.group.date_element is not None
        attrs = DATETIME_ATTRIBUTES[m.group.date_element]
        if len(attrs) != 1:
            raise IndexError(
                f"Date element '{m.group.date_element}' returned multiple elements."
            )
        return {attrs[0]: value}

    def process_B(self, m: GroupMatch) -> dict[str, int]:  # noqa: N802
        """Process match for full month."""
        return {"month": _find_month_number(m.match_str)}

    def process_F(self, m: GroupMatch) -> dict[str, int]:  # noqa: N802
        """Process match for full date (YYYY-mm-dd)."""
        value = m.match_str
        splits = value.split("-")
        if len(splits) != 3:
            raise ValueError(f"Could not parse date '{value}' (expected YYYY-mm-dd).")

        return dict(
            zip(
                ["year", "month", "day"],
                [int(x) for x in splits],
                strict=True,
            )
        )

    def process_x(self, m: GroupMatch) -> dict[str, int]:
        """Process match for full date (YYYYmmdd)."""
        value = m.match_str
        if len(value) < 5:
            raise ValueError(f"Could not parse date '{value}' (expected YYYYmmdd).")
        out = {"year": value[:-4], "month": value[-4:-2], "day": value[-2:]}
        return {elt: int(val) for elt, val in out.items()}

    def process_X(self, m: GroupMatch) -> dict[str, int]:  # noqa: N802
        """Process match for time (HHMMSS)."""
        value = m.match_str
        if len(value) != 6:
            raise ValueError(f"Could not parse time '{value}' (expected HHMMSS).")
        out = {"hour": value[:2], "minute": value[2:4], "second": value[4:6]}
        return {elt: int(val) for elt, val in out.items()}

    def process_j(self, m: GroupMatch) -> dict[str, int]:
        """Process match for day of year."""
        doy = m.get_match(parse=True)
        # This depend on the value of year, we take the first one discovered, or from
        # the default one if none was processed yet
        year = (
            self.elements["year"][0]
            if "year" in self.elements
            else self.default_date["year"]
        )
        return date_from_doy(doy, year)


def _find_month_number(name: str) -> int:
    """Find a month number from its name.

    Name can be the full name (January) or its three letter abbreviation (jan).
    The casing does not matter.
    """
    names = [m.lower() for m in calendar.month_name]
    names_abbr = [c[:3] for c in names]

    name = name.lower()
    if name in names:
        return names.index(name)
    if name in names_abbr:
        return names_abbr.index(name)

    raise ValueError(f"Could not interpret month name '{name}'")
