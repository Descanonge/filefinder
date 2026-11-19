"""Date related utilities."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | dt.date | Mapping[str, int | str | float]
"""Type for default_date argument."""


def _has_any_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) > 0


def _has_all_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) == len(keys)


class DateElement:
    """Date element."""

    key: ClassVar[str]
    regex: ClassVar[str]
    fmt: ClassVar[str] = "s"
    contains: ClassVar[tuple[str, ...]] = ()
    is_time: ClassVar[bool]

    ELEMENTS: ClassVar[dict[str, DateElement]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if hasattr(cls, "key"):
            cls.ELEMENTS[cls.key] = cls()

    @classmethod
    def get(cls, key: str) -> DateElement:
        """Obtain a DateElement instance for the corresponding element key."""
        if key not in cls.ELEMENTS:
            raise KeyError(
                f"'{key}' is not a registered date element. "
                f"Should be one of {list(cls.ELEMENTS.keys())}."
            )
        return cls.ELEMENTS[key]

    @classmethod
    def registered(cls) -> list[str]:
        """List of registered element names."""
        return list(cls.ELEMENTS.keys())

    def __repr__(self) -> str:
        return f"DateElement[{self.key}]"

    @property
    def is_time(self) -> bool:
        """Does this element is associated to properties of datetime (not just date)."""
        any_time = set(self.contains) & {
            "hour",
            "minute",
            "second",
            "microsecond",
            "tzinfo",
        }
        return len(any_time) > 0

    def format(self, value: int | float | str) -> str:
        """Format a value according to the date element format."""
        return f"{{:{self.fmt}}}".format(value)

    def datetime_to_str(self, date: dt.datetime | dt.date) -> str:
        """Extract element from a datetime object and format it."""
        return self.format(self.datetime_to_value(date))

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int | float | str:
        """Extract element from a datetime object."""
        raise NotImplementedError

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:
        """Prepare element for strptime.

        Some date elements need some preprocessing before being sent to strptime.

        Parameters
        ----------
        s:
            String match of date element.

        Returns
        -------
        update:
            Dictionnary of elements to add or change.
        """
        return {self.key: s}


## Date attributes
class DateElementDateAttr(DateElement):
    """Element is a simple date attribute."""

    date_attr: ClassVar[Literal["year", "month", "day"]]

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:  # noqa: D102
        return getattr(date, self.date_attr)


class DateElementY(DateElementDateAttr):
    """Year (YYYY)."""

    key = "Y"
    regex = r"\d{4}"
    fmt = "04d"
    date_attr = "year"
    contains = ("year",)


class DateElementm(DateElementDateAttr):
    """Month (mm)."""

    key = "m"
    regex = r"\d\d"
    fmt = "02d"
    date_attr = "month"
    contains = ("month",)


class DateElementd(DateElementDateAttr):
    """Day of month (dd)."""

    key = "d"
    regex = r"\d\d"
    fmt = "02d"
    date_attr = "day"
    contains = ("day",)


## Time attributes
class DateElementTimeAttr(DateElement):
    """Element is a simple time attribute."""

    time_attr: ClassVar[Literal["hour", "minute", "second", "microsecond"]]

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        return getattr(date, self.time_attr)


class DateElementH(DateElementTimeAttr):
    """Hour (HH)."""

    key = "H"
    regex = r"\d\d"
    fmt = "02d"
    time_attr = "hour"
    contains = ("hour",)


class DateElementM(DateElementTimeAttr):
    """Minute (MM)."""

    key = "M"
    regex = r"\d\d"
    fmt = "02d"
    time_attr = "minute"
    contains = ("minute",)


class DateElementS(DateElementTimeAttr):
    """Second (SS)."""

    key = "S"
    regex = r"\d\d"
    fmt = "02d"
    time_attr = "second"
    contains = ("second",)


class DateElementf(DateElementTimeAttr):
    """Microsecond (ffffff)."""

    key = "f"
    regex = r"\d{6}"
    fmt = "06d"
    time_attr = "microsecond"
    contains = ("microsecond",)


## Strings obtained from strftime
class DateElementStr(DateElement):
    """Element is a string that can directly be obtained with strftime."""

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        return date.strftime(f"%{self.key}")


class DateElementa(DateElementStr):
    """Weekday name, abbreviated. Current locale."""

    key = "a"
    regex = r"\w+"
    contains = ("month", "day")


class DateElementA(DateElementStr):
    """Weekday name. Current locale."""

    key = "A"
    regex = r"\w+"
    contains = ("month", "day")


class DateElementb(DateElementStr):
    """Month name, abbreviated. Current locale."""

    key = "b"
    description = "Month name abbreviated"
    regex = r"\w+"
    contains = ("month",)


class DateElementB(DateElementStr):
    """Month name. Current locale."""

    key = "B"
    regex = r"\w+"
    contains = ("month",)


## Integers obtained from strftime
class DateElementStrInt(DateElement):
    """Element is an integer that can be obtained from strftime."""

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:  # noqa: D102
        return int(date.strftime(f"%{self.key}"))


class DateElementI(DateElementStrInt):
    """Hour, 12-hour clock (01-12)."""

    key = "I"
    regex = r"\d\d"
    fmt = "02d"
    contains = ("hour",)

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        return super().datetime_to_value(date)


class DateElementj(DateElementStrInt):
    """Day of year (jjj)."""

    key = "j"
    regex = r"\d{3}"
    fmt = "03d"
    contains = ("month", "day")


class DateElementu(DateElementStrInt):
    """Weekday (1-7, Monday=1)."""

    key = "u"
    regex = r"\d"
    fmt = "01d"
    contains = ("month", "day")


class DateElementU(DateElementStrInt):
    """Week number, starting from first Sunday."""

    key = "U"
    regex = r"\d\d"
    fmt = "02d"
    contains = ("month", "day")


class DateElementw(DateElementStrInt):
    """Weekday (0-6, Sunday=0)."""

    key = "w"
    regex = r"\d"
    fmt = "01d"
    contains = ("month", "day")


class DateElementW(DateElementStrInt):
    """Week number, starting from first Monday."""

    key = "W"
    regex = r"\d\d"
    fmt = "02d"
    contains = ("month", "day")


## Others
class DateElementp(DateElement):
    """AM/PM."""

    key = "p"
    regex = r"AM|PM"
    contains = ("hour",)

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        return "AM" if date.hour < 12 else "PM"


class DateElementP(DateElement):
    """am/pm."""

    key = "P"
    regex = r"am|pm"
    contains = ("hour",)

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        return "am" if date.hour < 12 else "pm"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: D102
        return {"p": s.upper()}


class DateElements(DateElement):
    """Timestamp (seconds since epoch)."""

    key = "s"
    regex = r"[+-]?\d+(?:\.\d{6})?"
    fmt = ".6f"
    contains = ("year", "month", "day", "hour", "minute", "second", "microsecond")

    def datetime_to_value(self, date: dt.datetime | dt.date) -> float:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        if date.tzinfo is None:
            # Assume naive is UTC. timestamp will otherwise take it as local time
            date = date.replace(tzinfo=dt.UTC)
        return date.timestamp()


class DateElementz(DateElement):
    """Timezone (±HHMM[SS[.ffffff]])."""

    key = "z"
    regex = r"[+-]\d{4}(?:\d\d(?:\.\d{6})?)?"
    contains = ("tzinfo",)

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        return date.strftime("%z") if date.tzinfo is not None else "+0000"


## Composites
class DateElementF(DateElement):
    """Date (YYYY-mm-dd). Not locale dependant."""

    key = "F"
    regex = r"\d{4}-\d\d-\d\d"
    contains = ("year", "month", "day")

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        return f"{date.year:04d}-{date.month:02d}-{date.day:02d}"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: D102
        splits = s.split("-")
        if len(splits) != 3:
            raise ValueError(f"Could not parse date '{s}' (expected YYYY-mm-dd).")

        return dict(zip(["Y", "m", "d"], splits, strict=True))


class DateElementx(DateElement):
    """Date (YYYYmmdd). Not locale dependant."""

    key = "x"
    regex = r"\d{8}"
    contains = ("year", "month", "day")

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        return f"{date.year:04d}{date.month:02d}{date.day:02d}"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: D102
        if len(s) < 5:
            raise ValueError(f"Could not parse date '{s}' (expected YYYYmmdd).")
        return {"Y": s[:-4], "m": s[-4:-2], "d": s[-2:]}


class DateElementT(DateElement):
    """Time (HHMMSS). Not locale dependant."""

    key = "T"
    regex = r"\d{6}"
    contains = ("hour", "minute", "seconde")

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:  # noqa: D102
        if not isinstance(date, dt.datetime):
            raise TypeError
        return f"{date.hour:02d}{date.minute:02d}{date.second:02d}"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: D102
        if len(s) != 6:
            raise ValueError(f"Could not parse time '{s}' (expected HHMMSS).")
        return {"H": s[:2], "M": s[2:4], "S": s[4:]}


def datetime_to_str(date: dt.datetime | dt.date, element: str) -> str:
    return DateElement.get(element).datetime_to_str(date)


def datetime_to_value(date: dt.datetime | dt.date, element: str) -> int | float | str:
    return DateElement.get(element).datetime_to_value(date)


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

        default_date_str = {}
        for k, v in default_date.items():
            if not isinstance(v, str):
                v = DateElement.ELEMENTS[k].format(v)
            default_date_str[k] = v
        return default_date_str

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
            if element.key not in elements_all:
                elements_all[element.key] = []
            elements_all[element.key].append(m)

        print(elements_all)
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
            return dt.UTC

        date = dt.datetime.strptime("_".join(date_str), "_".join(date_fmt))
        return date.tzinfo

    def parse_s(self, s: str, tz: dt.tzinfo | None) -> dt.datetime:
        """Process timestamp."""
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

        contains = set()
        for elt in self.elements:
            if elt in present:
                continue
            contains |= set(DateElement.get(elt).contains)

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

        contains = set()
        for elt in self.elements:
            if elt in present:
                continue
            contains |= set(DateElement.get(elt).contains)

        if has_hour12 != has_ampm:
            if "hour" in contains:
                # We have other groups that can find the hour
                for elt in present:
                    elements.pop(elt)
            else:
                to_str = {True: "hour", False: "AM/PM"}
                has = to_str[has_hour12]
                missing = to_str[not has_hour12]
                raise ValueError(
                    f"Cannot correctly parse 12-hour with only the {has} and "
                    f"not the {missing}. You can add the missing element to the "
                    "default date mapping."
                )
