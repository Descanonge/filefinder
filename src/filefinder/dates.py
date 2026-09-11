"""Date related utilities."""

from __future__ import annotations

import calendar
import datetime as dt
import re
import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | Mapping[str, int] | None

datetime_keys = "YBmdjHMSFxX"
time_keys = "XHMS"

datetime_attributes = {
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

datetime_format = {
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
        if group in datetime_keys:
            return f"%({name}{group})"
        raise KeyError(f"Unknown datetime key '{match.group(0)}'.")

    return re.sub("%([a-zA-Z%])", replace, date_format)


def _check_input(date: dt.datetime | dt.date, name: str) -> None:
    if name in time_keys and not isinstance(date, dt.datetime):
        raise TypeError(
            f"'{name}' group needs time information (received a {type(date)} object)"
        )
    if name not in datetime_attributes:
        raise KeyError(f"'{name}' group name not registered in util.datetime_format")


def datetime_to_str(date: dt.datetime | dt.date, name: str) -> str:
    """Format a group from a date object."""
    _check_input(date, name)

    if name == "j":
        return f"{get_doy(date):03d}"
    if name == "B":
        return date.strftime("%B")

    elements = [getattr(date, attr) for attr in datetime_attributes[name]]
    fmt = datetime_format[name]
    return fmt.format(*elements)


def datetime_to_value(date: dt.datetime | dt.date, name: str) -> int | str:
    """Extract value of date group name (Y, m, F, ...) from a datetime object."""
    _check_input(date, name)

    if name == "j":
        return get_doy(date)

    if name in "xXFB":
        s = datetime_to_str(date, name)
        # xX can be returned as int, as per their format in Group.DATE_GROUPS
        return int(s) if name in "xX" else s

    elements = [getattr(date, attr) for attr in datetime_attributes[name]]
    assert len(elements) == 1
    return elements[0]


def get_doy(date: dt.date | dt.datetime) -> int:
    """Return the dayofyear of a date."""
    if isinstance(date, dt.datetime):
        date = date.date()
    return (date - dt.date(date.year, 1, 1)).days + 1


def date_from_doy(doy: int, year: int) -> dict[str, int]:
    """Get month and day from a dayofyear value (and its year)."""
    day = dt.date(year, 1, 1) + dt.timedelta(days=(doy - 1))
    return {"month": day.month, "day": day.day}


def get_date(
    matches: Sequence[GroupMatch], default_date: Mapping[str, int] | None = None
) -> dt.datetime:
    """Retrieve date from matched elements.

    Matches that can be used are in ``YBmdjHMSFxX``. If a matcher is *not* found in the
    filename, it will be replaced by the element of the default date argument. All
    values deduced from these matches will be compared. If different matchers give
    different values (for instance the group Y and F give a different year), an
    exception will be raised.

    Parameters
    ----------
    matches:
        Matches obtained from a filename.
    default_date:
        Default date. Dictionnary with keys: year, month, day, hour, minute,
        and second. Defaults to 1970-01-01 00:00:00
    """
    if default_date is None:
        default_date = {}
    # fill missing inputs
    default_date = {
        "year": 1970,
        "month": 1,
        "day": 1,
        "hour": 0,
        "minute": 0,
        "second": 0,
    } | dict(default_date)

    # list of values found in the matches: year, month, ...
    elts: dict[str, list[int]] = {}

    def process(key: str, callback: Callable[[GroupMatch], dict[str, int]]) -> None:
        """Run *callback* on matches selected by *key*.

        The callback returns a dictionnary with the datetime arguments (elements) it
        found. Each new value is added to the list of values found for that element.
        """
        for m in matches:
            if m.group.date_element != key:
                continue
            for elt, val in callback(m).items():
                if elt not in elts:
                    elts[elt] = []
                elts[elt].append(val)

    def process_B(m: GroupMatch) -> dict[str, int]:  # noqa: N802
        return {"month": _find_month_number(m.match_str)}

    def process_F(m: GroupMatch) -> dict[str, int]:  # noqa: N802
        # YYYY-mm-dd
        # 0123456789
        value = m.match_str
        out = {"year": value[:4], "month": value[5:7], "day": value[8:10]}
        return {elt: int(val) for elt, val in out.items()}

    def process_x(m: GroupMatch) -> dict[str, int]:
        # YYYYmmdd
        # 012345678
        value = m.match_str
        out = {"year": value[:4], "month": value[4:6], "day": value[6:8]}
        return {elt: int(val) for elt, val in out.items()}

    def process_X(m: GroupMatch) -> dict[str, int]:  # noqa: N802
        # HHMMSS (seconds optional)
        # 0123456
        value = m.match_str
        out = {"hour": value[:2], "minute": value[2:4]}
        if len(value) > 4:
            out["second"] = value[4:6]
        return {elt: int(val) for elt, val in out.items()}

    def process_j(m: GroupMatch) -> dict[str, int]:
        doy = m.get_match(parse=True)
        # This depend on the value of year, we take the first one discovered, or from
        # the default one if none was processed yet
        year = elts["year"][0] if "year" in elts else default_date["year"]
        return date_from_doy(doy, year)

    def process_simple(m: GroupMatch) -> dict[str, int]:
        value = m.get_match(parse=True)
        assert m.group.date_element is not None
        elts = datetime_attributes[m.group.date_element]
        assert len(elts) == 1
        return {elts[0]: value}

    process("B", process_B)
    process("F", process_F)
    process("x", process_x)
    process("X", process_X)

    for name in "YmdHMS":
        process(name, process_simple)

    # process j last, it needs month and year set
    process("j", process_j)

    if len(elts) == 0:
        warnings.warn(
            "No date elements could be recovered. Returning default date.", stacklevel=1
        )

    for elt, values in elts.items():
        if any(v != values[0] for v in values):
            raise ValueError(f"Different values found for {elt}: {values}")

    date = dict(default_date)
    for elt, values in elts.items():
        date[elt] = values[0]

    return dt.datetime(**date)  # type: ignore[arg-type]


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
