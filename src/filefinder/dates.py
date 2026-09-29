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

DATETIME_ELEMENTS = "aAbBdfFHIjmMpPsSTuUwWYz"
TIME_ELEMENTS = "HIMpPSTz"
STRING_ELEMENTS = "aAbBFpPTxz"


def _has_any_keys(d: dict, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) > 0


def _datetime_to_dict(date: dt.datetime) -> dict:
    return {
        attr: getattr(date, attr)
        for attr in [
            "year",
            "month",
            "day",
            "hour",
            "minute",
            "second",
            "microsecond",
            "tzinfo",
        ]
    }


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
        if group in DATETIME_ELEMENTS:
            return f"%({name}{group})"
        raise KeyError(f"Unknown datetime key '{match.group(0)}'.")

    return re.sub("%([a-zA-Z%])", replace, date_format)


def _check_input(date: dt.datetime | dt.date, name: str) -> None:
    if name in TIME_ELEMENTS and not isinstance(date, dt.datetime):
        raise TypeError(
            f"'{name}' group needs time information (received a {type(date)} object)"
        )
    if name not in DATETIME_ELEMENTS:
        raise KeyError(f"'{name}' group name not registered in util.datetime_format")


def datetime_to_str(date: dt.datetime | dt.date, group_name: str) -> str:
    """Format a date element (Y, m, F, ...) from a datetime object."""
    _check_input(date, group_name)

    if group_name == "T":
        return date.strftime("%H%M%S")
    if group_name == "x":
        return date.strftime("%Y%m%d")
    if group_name == "z":
        return date.strftime("%z") if date.tzinfo is not None else "+0000"
    return date.strftime(f"%{group_name}")


def datetime_to_value(date: dt.datetime | dt.date, group_name: str) -> int | str:
    """Extract value of date element (Y, m, F, ...) from a datetime object."""
    _check_input(date, group_name)

    s = datetime_to_str(date, group_name)
    if group_name in "aAbBFpPTxz":
        return s

    return int(s)


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

    DEFAULT_DATE_DEFAULT: ClassVar[dict] = {
        "year": 1970,
        "month": 1,
        "day": 1,
        "hour": 0,
        "minute": 0,
        "second": 0,
        "tzinfo": None,
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
            default_date = _datetime_to_dict(default_date)
        elif isinstance(default_date, dt.date):
            default_date = {
                attr: getattr(default_date, attr) for attr in ["year", "month", "day"]
            }

        self.default_date = self.DEFAULT_DATE_DEFAULT | dict(default_date)

        self.elements: dict[str, str] = {}
        self.date_args: dict[str, int | dt.timezone] = {}

        self.matches_to_elements()

    @classmethod
    def parse(
        cls, matches: Sequence[GroupMatch], default_date: DefaultDate | None = None
    ) -> dt.datetime:
        """Retrieve a date from matches."""
        parser = cls(matches, default_date)
        parser.matches_to_elements()
        return parser.retrieve_date()

    def matches_to_elements(self) -> None:
        for m in self.matches:
            name = m.group.name
            if name in self.elements and m.match_str != self.elements[name]:
                raise ValueError
            self.elements[name] = m.match_str

    def retrieve_date(self) -> dt.datetime:
        """Retrieve a date from matches."""
        self.elements = {}
        self.date_args = {}
        self.matches_to_elements()

        self.process("z", self.process_z)  # Better to have timezone for timestamp
        self.process("s", self.process_s)
        self.process("YmdHMSf", self.process_basic)
        self.process("b", self.process_b)
        self.process("B", self.process_B)
        self.process("F", self.process_F)
        self.process("x", self.process_x)
        self.process("T", self.process_T)
        self.process("j", self.process_j)
        self.process("IpP", self.process_hour_12)
        self.process("aAuUVwW", self.process_week_day)

        return self.create_date()

    def process(self, names: str, callback: Callable[..., dict]) -> None:
        if _has_any_keys(self.elements, names):
            # TODO: check there is no rewrite
            self.date_args |= callback()

    def get(self, arg: str) -> int | dt.timezone | None:
        if arg in self.date_args:
            return self.date_args[arg]
        if arg in self.default_date:
            return self.default_date[arg]
        raise KeyError

    def create_date(self) -> dt.datetime:
        """Create a datetime object from found elements."""
        args = self.default_date | self.date_args
        return dt.datetime(**args)  # type: ignore[arg-type]

    def process_z(self) -> dict[str, dt.timezone]:
        m = re.fullmatch(r"([+-])(\d\d)(\d\d)(\d\d(?:\.\d{6})?)?", self.elements["z"])
        if m is None:
            raise ValueError

        sign = m.group(1)
        elements = dict(
            zip(
                ["hours", "minutes", "seconds"],
                [float(x) for x in m.groups()[1:] if x is not None],
                strict=False,
            )
        )
        delta = dt.timedelta(**elements)
        if sign == "-":
            delta = -delta

        tz = dt.timezone(delta)
        return {"tzinfo": tz}

    def process_s(self) -> dict[str, int]:
        date = dt.datetime.fromtimestamp(
            float(self.elements["s"]), tz=self.get("tzinfo")
        )
        return {
            attr: getattr(date, attr)
            for attr in [
                "year",
                "month",
                "day",
                "hour",
                "minute",
                "second",
                "microsecond",
            ]
        }

    def process_basic(self) -> dict[str, int]:
        attributes = {
            "Y": "year",
            "m": "month",
            "d": "day",
            "H": "hour",
            "M": "minute",
            "S": "second",
            "f": "microsecond",
        }
        result = {}
        for element, attr in attributes.items():
            if element in self.elements:
                result[attr] = int(self.elements.pop(element))
        return result

    def process_B(self) -> dict[str, int]:  # noqa: N802
        name = self.elements.pop("B").lower()
        names = [m.lower() for m in calendar.month_name]
        if name in names:
            return {"month": names.index(name)}

        raise KeyError

    def process_b(self) -> dict[str, int]:
        name = self.elements.pop("b").lower()
        names = [m.lower() for m in calendar.month_name[1:]]

        for i, ref in enumerate(names):
            if ref.startswith(name):
                return {"month": i + 1}
        raise KeyError

    def process_F(self) -> dict[str, int]:  # noqa: N802
        """Process match for full date (YYYY-mm-dd)."""
        s = self.elements["F"]
        splits = s.split("-")
        if len(splits) != 3:
            raise ValueError(f"Could not parse date '{s}' (expected YYYY-mm-dd).")

        return dict(
            zip(
                ["year", "month", "day"],
                [int(x) for x in splits],
                strict=True,
            )
        )

    def process_x(self) -> dict[str, int]:
        """Process match for full date (YYYYmmdd)."""
        s = self.elements["x"]
        if len(s) < 5:
            raise ValueError(f"Could not parse date '{s}' (expected YYYYmmdd).")
        out = {"year": s[:-4], "month": s[-4:-2], "day": s[-2:]}
        return {elt: int(val) for elt, val in out.items()}

    def process_T(self) -> dict[str, int]:  # noqa: N802
        """Process match for time (HHMMSS)."""
        s = self.elements["T"]
        if len(s) != 6:
            raise ValueError(f"Could not parse time '{s}' (expected HHMMSS).")
        out = {"hour": s[:2], "minute": s[2:4], "second": s[4:6]}
        return {elt: int(val) for elt, val in out.items()}

    def process_j(self) -> dict[str, int]:
        s = self.elements["j"]
        date = dt.date(self.get("year"), 1, 1) + dt.timedelta(days=int(s) - 1)
        return {"month": date.month, "day": date.day}

    def process_hour_12(self) -> dict[str, int]:
        has_p = _has_any_keys(self.elements, "pP")
        has_i = _has_any_keys(self.elements, "I")
        if has_p != has_i:
            raise ValueError

        ampm = self.elements.get("p") or self.elements["P"]

        # ampm = self.elements.get("p", self.elements["P"])
        hour = int(self.elements["I"]) % 12
        if ampm.lower() == "pm":
            hour += 12
        return {"hour": hour}

    def process_week_day(self) -> dict[str, int]:
        values = {c: self.elements[c] for c in "aAuwUVW" if c in self.elements}

        if not _has_any_keys(values, "aAuw"):
            if "weekday" in self.default_date:
                values["w"] = str(self.default_date["weekday"])
            else:
                raise ValueError

        if not _has_any_keys(values, "UVW"):
            if "weeknumber" in self.default_date:
                values["W"] = f"{self.default_date['weeknumber']:02d}"
            else:
                raise ValueError

        fmt = "%Y_" + "_".join(f"%{c}" for c in values)
        date_string = f"{self.get('year'):04d}" + "_" + "_".join(values.values())

        date = dt.datetime.strptime(date_string, fmt)
        return {"month": date.month, "day": date.day}


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
