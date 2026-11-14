"""Date related utilities."""

from __future__ import annotations

import calendar
import datetime as dt
import re
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | dt.date | Mapping[str, int | str | float | dt.timezone]
"""Type for default_date argument."""

DATETIME_ELEMENTS = "aAbBdfFHIjmMpPsSTuUxwWYz"
TIME_ELEMENTS = "HIMpPsSTz"
STRING_ELEMENTS = "aAbBFpPTxz"


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
        if group in DATETIME_ELEMENTS:
            return f"%({name}{group})"
        raise KeyError(f"Unknown datetime key '{match.group(0)}'.")

    return re.sub("%([a-zA-Z%])", replace, date_format)


def datetime_to_str(date: dt.datetime | dt.date, element: str) -> str:
    """Format a date element (Y, m, F, ...) from a datetime object.

    Naive datetimes are considered UTC.
    """
    if element not in DATETIME_ELEMENTS:
        raise KeyError(
            f"Group name '{element}' not registered in dates.DATETIME_ELEMENTS"
        )
    if element in TIME_ELEMENTS:
        if not isinstance(date, dt.datetime):
            raise TypeError(
                f"Element '{element}' needs time information, ie a datetime.datetime "
                "object, not datetime.date."
            )
        # P is not platform independant
        if element in "pP":
            ampm = "am" if date.hour < 12 else "pm"
            if element == "p":
                ampm = ampm.upper()
            return ampm

        if element == "z":
            return date.strftime("%z") if date.tzinfo is not None else "+0000"

        # Assume naive is UTC. timestamp/strftime will otherwise take it as local time
        if date.tzinfo is None:
            date = date.replace(tzinfo=dt.UTC)

        if element == "s":
            return f"{date.timestamp():.6f}"

        if element == "T":
            return date.strftime("%H%M%S")

    # strftime does not zero-pad the year (but strptime needs it)
    if element == "Y":
        return f"{date.year:04d}"
    if element == "F":
        return f"{date.year:04d}-{date.month:02d}-{date.day:02d}"
    if element == "x":
        return f"{date.year:04d}{date.month:02d}{date.day:02d}"

    return date.strftime(f"%{element}")


def datetime_to_value(date: dt.datetime | dt.date, element: str) -> int | float | str:
    """Extract value of date element (Y, m, F, ...) from a datetime object.

    Naive datetimes are considered UTC.
    """
    if element not in DATETIME_ELEMENTS:
        raise KeyError(
            f"Group name '{element}' not registered in dates.DATETIME_ELEMENTS"
        )
    if element in TIME_ELEMENTS:
        if not isinstance(date, dt.datetime):
            raise TypeError(
                f"Element '{element}' needs time information, ie a datetime.datetime "
                "object, not datetime.date."
            )
        if element == "s":
            # Assume naive is UTC. timestamp/strftime will otherwise take it as local time
            if date.tzinfo is None:
                date = date.replace(tzinfo=dt.UTC)
            return date.timestamp()

    attributes = {
        "Y": "year",
        "m": "month",
        "d": "day",
        "H": "hour",
        "M": "minute",
        "S": "second",
        "f": "microsecond",
    }
    if element in attributes:
        return getattr(date, attributes[element])

    if element in "IjuUwW":
        return int(datetime_to_str(date, element))

    # aAbBFpPTxz
    return datetime_to_str(date, element)


class DateParser:
    """Parse date from matches.

    Matches are prepared before being passed to :func:`datetime.datetime.strptime.`.
    Some elements may not be available on all platforms, see
    :ref:`strftime-strptime-behavior`

    The `default_date` argument provides default values for any elements (by default,
    ``YmdHMSf``).

    If multiple **groups** have different values for the same element, an exception will
    be raised. However, strptime does not check for the coherence of multiple elements.
    For instance, if elements ``Ymd`` and ``j`` correspond to different dates, one of
    them will be chosen and the other ignored (as far as I know, this is undefined
    behavior).

    Unless a match contains timezone information (``%(z)``) or the `default_date` has
    been given `tzinfo`, the returned date will be naive. Filefinder considers naive
    objects as UTC, so if no timezone information is available it will parse everything
    as if UTC.

    To parse a date from the week day and week number, the parser needs both information
    on the day of the week (elements ``a, A, u`` or ``w``) and the week number (elements
    ``U`` or ``W``). If only one part of the information is present:

    - If other groups contain information about the month and day, the week part will
      simply be ignored. For instance the pattern ``"%(Y)%(m)%(d)_%(a)"``
      ("20261025_Sun") will ignore the information about the week day, and it will not
      check the day of week is coherent the rest of the date.
    - Otherwise, the parser will raise an exception. You may use the default date to
      supply the missing elements.

    Similarly, when parsing the hour from a 12-hour clock, the parser will need element
    ``I`` and either ``p`` or ``P``, otherwise an exception will be raised.

    If a timestamp element ``s`` is present, the timezone ``z`` will be parsed
    separately and the parser will use :meth:`~datetime.datetime.fromtimestamp` and
    ignore all other elements. Parsing may not be accurate to the microsecond when years
    are too far from the epoch.

    The names of months and week days are those of the current locale.

    Use with either::

        date = DateParser(matches, default_date).parse()

    Parameters
    ----------
    matches:
        Matches obtained from a filename.
    default_date:
        Default value for elements if not found in the filename. It can be a mapping of
        elements or a :mod:`datetime` object (in which case the elements ``YmdHMSfz``
        are used). Defaults to 1970-01-01 00:00:00 (naive).
    """

    DEFAULT_DATE_DEFAULT: ClassVar[dict] = {
        "Y": 1970,
        "m": 1,
        "d": 1,
        "H": 0,
        "M": 0,
        "S": 0,
        "f": 0,
    }

    """Default values for the default_date. Note it is offset-naive."""

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
                tz = datetime_to_str(default_date, "z")
            default_date = {
                elt: datetime_to_str(default_date, elt) for elt in "YmdHMSf"
            }
            if tz is not None:
                default_date["z"] = tz

        elif isinstance(default_date, dt.date):
            default_date = {elt: datetime_to_str(default_date, elt) for elt in "Ymd"}

        default_date = self.DEFAULT_DATE_DEFAULT | dict(default_date)

        # convert to str
        fmts = {
            "d": "02d",
            "f": "06d",
            "H": "02d",
            "I": "02d",
            "j": "03d",
            "m": "02d",
            "M": "02d",
            "S": "02d",
            "u": "01d",
            "U": "02d",
            "w": "01d",
            "W": "02d",
            "Y": "04d",
        }
        for k, v in default_date.items():
            if not isinstance(v, str):
                default_date[k] = f"{{:{fmts[k]}}}".format(v)

        return default_date

    def matches_to_elements(self) -> dict[str, str]:
        """Create dictionary of elements name to matched strings.

        Will check that multiple groups of the same element have the same value, and
        that all matches correspond to date groups.
        """
        elements_all: dict[str, list[GroupMatch]] = {}
        for m in self.matches:
            element = m.group.date_element
            if element is None:
                raise ValueError(f"'{m.group}' is not a date group.")
            if element not in elements_all:
                elements_all[element] = []
            elements_all[element].append(m)

        for element, matches in elements_all.items():
            values = [m.match_str for m in matches]
            if any(v != values[0] for v in values[1:]):
                raise ValueError(
                    f"Groups with the same element '{element}' received "
                    f"different values: {', '.join(str(m) for m in matches)}."
                )

        return {
            element: matches[0].match_str for element, matches in elements_all.items()
        }

    def prepare_elements(self, elements: dict[str, str]) -> None:
        """Prepare elements for datetime.strptime."""

        def update(elements: dict[str, str], update: Mapping[str, str]) -> None:
            for elt, value in update.items():
                elements.setdefault(elt, value)

        if (s := elements.pop("F", None)) is not None:
            update(elements, self.prepare_F(s))
        if (s := elements.pop("x", None)) is not None:
            update(elements, self.prepare_x(s))
        if (s := elements.pop("T", None)) is not None:
            update(elements, self.prepare_T(s))
        if (s := elements.pop("P", None)) is not None:
            update(elements, self.prepare_P(s))

    def prepare_F(self, s: str) -> dict[str, str]:  # noqa: N802
        """Convert F element into Y, m, d."""
        splits = s.split("-")
        if len(splits) != 3:
            raise ValueError(f"Could not parse date '{s}' (expected YYYY-mm-dd).")

        return dict(zip(["Y", "m", "d"], splits, strict=True))

    def prepare_x(self, s: str) -> dict[str, str]:
        """Convert x element into Y, m, d."""
        if len(s) < 5:
            raise ValueError(f"Could not parse date '{s}' (expected YYYYmmdd).")
        return {"Y": s[:-4], "m": s[-4:-2], "d": s[-2:]}

    def prepare_T(self, s: str) -> dict[str, str]:  # noqa: N802
        """Convert T element into H, M, S."""
        if len(s) != 6:
            raise ValueError(f"Could not parse time '{s}' (expected HHMMSS).")
        return {"H": s[:2], "M": s[2:4], "S": s[4:6]}

    def prepare_P(self, s: str) -> dict[str, str]:  # noqa: N802
        """Convert P element into p."""
        return {"p": s.upper()}

    def parse(self) -> dt.datetime:
        """Parse the date."""
        elements = self.default_elements | self.elements

        if "s" in elements:
            if "z" in elements:
                tz = self.parse_z(elements["z"])
            else:
                tz = None
            return self.parse_s(elements["s"], tz)

        self.check_elements(elements)

        date_fmt = "_".join([f"%{elt}" for elt in elements])
        date_str = "_".join(elements.values())

        return dt.datetime.strptime(date_str, date_fmt)

    def parse_z(self, z: str) -> dt.timezone:
        """Process timezone information."""
        m = re.fullmatch(r"([+-])(\d\d)(\d\d)(?:(\d\d)(?:\.(\d{6}))?)?", z)
        if m is None:
            raise ValueError(
                f"Could not parse timezone information '{z}' "
                "with pattern ±HHMM[SS[.ffffff]]."
            )

        sign = m.group(1)
        elements = dict(
            zip(
                ["hours", "minutes", "seconds", "microseconds"],
                [float(x) for x in m.groups()[1:] if x is not None],
                strict=False,
            )
        )
        delta = dt.timedelta(**elements)
        if sign == "-":
            delta = -delta

        return dt.timezone(delta)

    def parse_s(self, s: str, tz: dt.timezone | None) -> dt.datetime:
        """Process timestamp."""
        is_naive = tz is None
        if is_naive:
            tz = dt.UTC  # otherwise fromtimestamp assumes local time

        date = dt.datetime.fromtimestamp(float(s), tz=tz)  # type: ignore[arg-type]
        if is_naive:
            date = date.replace(tzinfo=None)

        return date

    def check_elements(self, elements: dict[str, str]) -> None:
        present = set("aAuwUW") & set(elements.keys())
        has_weekday = _has_any_keys(elements, "aAuw")
        has_weeknumber = _has_any_keys(elements, "UW")

        if has_weekday != has_weeknumber:
            if "j" in self.elements or (
                _has_any_keys(self.elements, "mbB") and "d" in self.elements
            ):
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

        present = set("IpP") & set(elements.keys())
        has_hour12 = "I" in elements
        has_ampm = _has_any_keys(elements, "pP")
        if has_hour12 != has_ampm:
            if "H" in self.elements:
                # We have other groups that can find the hour
                for elt in present:
                    elements.pop(elt)
            else:
                to_str = {True: "hour", False: "AM/PM"}
                has = to_str[has_weekday]
                missing = to_str[not has_weekday]
                raise ValueError(
                    f"Cannot correctly parse 12-hour with only the {has} and "
                    f"not the {missing}. You can add the missing element to the "
                    "default date mapping."
                )
