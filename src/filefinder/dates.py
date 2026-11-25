"""Date related utilities."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

from .date_elements import DateElement
from .group import DateGroup

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | dt.date | Mapping[str, int | str | float | dt.tzinfo]
"""Type for default_date argument."""


def _has_any_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) > 0


def _has_all_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) == len(keys)


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
        if group in DateElement.ELEMENTS:
            return f"%({name}{group})"
        raise KeyError(f"Unknown datetime key '{match.group(0)}'.")

    return re.sub("%([a-zA-Z%])", replace, date_format)


class DateParser:
    """Parse date from matches.

    Use with::

        date = DateParser(matches, default_date).parse()

    Parameters
    ----------
    matches:
        Matches obtained from a filename, corresponding to date elements. The groups
        must be instances of :class:`.DateGroup`.
    default_date:
        Default value for elements if not found in the filename. It can be a mapping of
        elements or a :mod:`datetime` object (in which case the elements ``YmdHMSfz``
        are used). Defaults to 1970-01-01 00:00:00 (naive). See :ref:`default_date` for
        details.
    """

    DEFAULT_DATE_DEFAULT: ClassVar[dict[str, str | int | float]] = {
        "Y": 1970,
        "m": 1,
        "d": 1,
        "H": 0,
        "M": 0,
        "S": 0,
        "f": 0,
    }
    """Default values for the default_date."""

    def __init__(
        self, matches: Sequence[GroupMatch], default_date: DefaultDate | None = None
    ) -> None:
        self.matches: list[GroupMatch] = list(matches)

        self.default_elements = self.get_default_elements(default_date)

        self.elements: dict[str, str] = self.matches_to_elements()
        """Dictionary of elements names to matched strings."""

        self.prepare_elements(self.elements)
        self.prepare_elements(self.default_elements)

    def get_default_elements(self, default_date: DefaultDate | None) -> dict[str, str]:
        """Create default elements."""
        if default_date is None:
            default_date = {}
        if isinstance(default_date, dt.datetime):
            tz = None
            if default_date.tzinfo is not None:
                tz = DateElement.ELEMENTS["z"].datetime_to_value(default_date)
            default_date = {
                elt: DateElement.ELEMENTS[elt].datetime_to_str(default_date)
                for elt in "YmdHMSf"
            }
            if tz is not None:
                default_date["z"] = tz

        elif isinstance(default_date, dt.date):
            default_date = {
                elt: DateElement.ELEMENTS[elt].datetime_to_str(default_date)
                for elt in "Ymd"
            }

        default_date = self.DEFAULT_DATE_DEFAULT | dict(default_date)

        default_date_str = {
            k: v if isinstance(v, str) else DateElement.ELEMENTS[k].format(v)
            for k, v in default_date.items()
        }
        return default_date_str

    def matches_to_elements(self) -> dict[str, str]:
        """Create dictionary of elements name to matched strings.

        Will check that multiple groups of the same element have the same value, and
        that all matches correspond to date groups.
        """
        elements_all: dict[str, list[GroupMatch]] = {}
        for m in self.matches:
            if not isinstance(m.group, DateGroup):
                raise ValueError(f"'{m.group}' is not a date group.")
            elt_obj = m.group.date_element
            if not elt_obj.parsable:
                continue
            if elt_obj.key not in elements_all:
                elements_all[elt_obj.key] = []
            elements_all[elt_obj.key].append(m)

        for element, matches in elements_all.items():
            values = [m.match_str for m in matches]
            if any(v != values[0] for v in values[1:]):
                raise ValueError(
                    f"Groups with the same element '{element}' received "
                    f"different values: {', '.join(str(m) for m in matches)}."
                )

        return {elt: matches[0].match_str for elt, matches in elements_all.items()}

    def prepare_elements(self, elements: dict[str, str]) -> None:
        """Prepare elements for datetime.strptime."""
        for key, elt in DateElement.ELEMENTS.items():
            if key in elements:
                prepared = elt.prepare(elements.pop(key))
                for k, v in prepared.items():
                    elements.setdefault(k, v)

    def parse(self) -> dt.datetime:
        """Parse the date."""
        elements = self.default_elements | self.elements

        self.check_weekday(elements)
        self.check_hour12(elements)

        if "s" in elements:
            tz = self.parse_z(elements)
            return self.parse_s(elements["s"], tz)

        date_fmt = "_".join([f"%{elt}" for elt in elements])
        date_str = "_".join(elements.values())

        return dt.datetime.strptime(date_str, date_fmt)

    def parse_z(self, elements: Mapping[str, str]) -> dt.tzinfo | None:
        """Parse timezone."""
        date_str = []
        date_fmt = []
        for elt, value in elements.items():
            if "tzinfo" in DateElement.get(elt).contains:
                date_str.append(value)
                date_fmt.append(f"%{elt}")

        if not date_str:
            # no element with timezone info
            return None

        date = dt.datetime.strptime("_".join(date_str), "_".join(date_fmt))
        return date.tzinfo

    def parse_s(self, s: str, tz: dt.tzinfo | None) -> dt.datetime:
        """Parse timestamp."""
        is_naive = tz is None
        if is_naive:
            tz = dt.UTC  # otherwise fromtimestamp assumes local time

        date = dt.datetime.fromtimestamp(float(s), tz=tz)  # type: ignore[arg-type]
        if is_naive:
            date = date.replace(tzinfo=None)

        return date

    def check_weekday(self, elements: dict[str, str]) -> None:
        """Check enough elements are present."""
        present = set("aAuwUW") & set(elements.keys())
        has_weekday = _has_any_keys(elements, "aAuw")
        has_weeknumber = _has_any_keys(elements, "UW")

        contains = DateElement.all_contains(set(self.elements.keys()) - present)

        if has_weekday != has_weeknumber:
            if {"month", "day"} & contains:
                # We have other groups that can find the date
                # we can ignore week day/number
                for elt in present:
                    elements.pop(elt)
            else:
                to_str = {True: "week day", False: "week number"}
                has = to_str[has_weekday]
                missing = to_str[not has_weekday]
                raise ValueError(
                    f"Cannot correctly parse week day/number with only the {has} and "
                    f"not the {missing}. You can add the missing element to the "
                    "default date mapping."
                )

    def check_hour12(self, elements: dict[str, str]) -> None:
        """Check enough elements are present."""
        present = set("IpP") & set(elements.keys())
        has_hour12 = "I" in elements
        has_ampm = _has_any_keys(elements, "pP")

        contains = DateElement.all_contains(set(self.elements.keys()) - present)

        if has_hour12 != has_ampm:
            if "hour" in contains:
                # We have other groups that can find the hour
                for elt in present:
                    elements.pop(elt)
            else:
                to_str = {True: "the hour (%I)", False: "AM/PM"}
                has = to_str[has_hour12]
                missing = to_str[not has_hour12]
                raise ValueError(
                    f"Cannot correctly parse 12-hour with only {has} and "
                    f"not {missing}. You can add the missing element to the "
                    "default date mapping."
                )
