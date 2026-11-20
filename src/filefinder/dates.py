"""Date related utilities."""

from __future__ import annotations

import datetime as dt
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, ClassVar, Literal

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | dt.date | Mapping[str, int | str | float | dt.tzinfo]
"""Type for default_date argument."""


def _has_any_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) > 0


def _has_all_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) == len(keys)


__all__ = [
    "DateElement",
    "DateParser",
    "DefaultDate",
    "datetime_to_str",
    "datetime_to_value",
    "make_date_groups",
]


class DateElement:
    """Date element base class and registry.

    A class representing a date element that can be used in a date group, and parsed
    into a datetime object.
    """

    key: ClassVar[str]
    """Name of the element."""
    regex: ClassVar[str]
    """Default regular-expression."""
    fmt: ClassVar[str] = "s"
    """Default format string."""
    contains: ClassVar[tuple[str, ...]] = ()
    """What :class:`datetime.datetime` arguments can be inferred from this element."""
    parsable: ClassVar[bool] = True
    """If this element should be used for date parsing. If False, matches will be
    ignored by the parser."""
    description: ClassVar[str] = "placeholder"
    """Description used in the documentation."""

    ELEMENTS: ClassVar[dict[str, DateElement]] = {}
    """Dictionary of instances of registered element classes."""

    def __init_subclass__(cls, **kwargs: Any) -> None:
        if hasattr(cls, "key"):
            cls.ELEMENTS[cls.key] = cls()

    # Technically, all methods could be class methods (DateElement has no instance
    # attributes). I reserve class methods for registry-related stuff.

    @classmethod
    def get(cls, key: str) -> DateElement:
        """Obtain a DateElement instance for the corresponding element key.

        Raises
        ------
        KeyError
            If not a registered element.
        """
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

    @classmethod
    def all_contains(cls, keys: Iterable[str]) -> set[str]:
        """Set of the datetime arguments that can be infered from multiple elements."""
        contains = set()
        for key in keys:
            contains |= set(cls.get(key).contains)
        return contains

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

    def format(self, value: Any) -> str:
        """Format a value according to the date element format.

        This should only be used for formatting default date elements that may be passed
        by the user as unformatted values. Groups will use their own format string (that
        can be changed by the user in the group specifications).
        """
        return f"{{:{self.fmt}}}".format(value)

    def datetime_to_str(self, date: dt.datetime | dt.date) -> str:
        """Extract element from a datetime object and format it."""
        return self.format(self.datetime_to_value(date))

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int | float | str:
        """Extract element from a datetime object."""
        raise NotImplementedError

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: ARG002
        """Prepare element for strptime.

        By default, this returns the same element with no change.

        Parameters
        ----------
        s:
            String match of date element.
        kwargs:
            Currently empty. In the future, could be additional information passed by
            the parser.

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

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:
        return getattr(date, self.date_attr)


class DateElementY(DateElementDateAttr):
    """Year (YYYY)."""

    key = "Y"
    regex = r"\d{4}"
    fmt = "04d"
    date_attr = "year"
    contains = ("year",)
    description = "Year (YYYY)"


class DateElementm(DateElementDateAttr):
    """Month (mm)."""

    key = "m"
    regex = r"\d\d"
    fmt = "02d"
    date_attr = "month"
    contains = ("month",)
    description = "Month (mm)"


class DateElementd(DateElementDateAttr):
    """Day of month (dd)."""

    key = "d"
    regex = r"\d\d"
    fmt = "02d"
    date_attr = "day"
    contains = ("day",)
    description = "Day (dd)"


## Time attributes
class DateElementTimeAttr(DateElement):
    """Element is a simple time attribute."""

    time_attr: ClassVar[Literal["hour", "minute", "second", "microsecond"]]

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:
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
    description = "Hour, 24-hour clock (HH)"


class DateElementM(DateElementTimeAttr):
    """Minute (MM)."""

    key = "M"
    regex = r"\d\d"
    fmt = "02d"
    time_attr = "minute"
    contains = ("minute",)
    description = "Minute (MM)"


class DateElementS(DateElementTimeAttr):
    """Second (SS)."""

    key = "S"
    regex = r"\d\d"
    fmt = "02d"
    time_attr = "second"
    contains = ("second",)
    description = "Second (SS)"


class DateElementf(DateElementTimeAttr):
    """Microsecond (ffffff)."""

    key = "f"
    regex = r"\d{6}"
    fmt = "06d"
    time_attr = "microsecond"
    contains = ("microsecond",)
    description = "Microsecond (ffffff)"


## Strings obtained from strftime
class DateElementStr(DateElement):
    """Element is a string that can directly be obtained with strftime."""

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        return date.strftime(f"%{self.key}")


class DateElementa(DateElementStr):
    """Weekday name, abbreviated. Current locale."""

    key = "a"
    regex = r"\w+"
    contains = ("month", "day")
    description = "Week day name, in current locale, abbreviated"


class DateElementA(DateElementStr):
    """Weekday name. Current locale."""

    key = "A"
    regex = r"\w+"
    contains = ("month", "day")
    description = "Week day name, in current locale"


class DateElementb(DateElementStr):
    """Month name, abbreviated. Current locale."""

    key = "b"
    regex = r"\w+"
    contains = ("month",)
    description = "Month name, in current locale, abbreviated"


class DateElementB(DateElementStr):
    """Month name. Current locale."""

    key = "B"
    regex = r"\w+"
    contains = ("month",)
    description = "Month name, in current locale"


## Integers obtained from strftime
class DateElementStrInt(DateElement):
    """Element is an integer that can be obtained from strftime."""

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:
        return int(date.strftime(f"%{self.key}"))


class DateElementI(DateElementStrInt):
    """Hour, 12-hour clock (01-12)."""

    key = "I"
    regex = r"\d\d"
    fmt = "02d"
    contains = ("hour",)
    description = "Hour, 12-hour clock (01-12)"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> int:
        if not isinstance(date, dt.datetime):
            raise TypeError
        return super().datetime_to_value(date)


class DateElementj(DateElementStrInt):
    """Day of year (jjj)."""

    key = "j"
    regex = r"\d{3}"
    fmt = "03d"
    contains = ("month", "day")
    description = "Day of year (jjj)"


class DateElementu(DateElementStrInt):
    """Weekday (1-7, Monday=1)."""

    key = "u"
    regex = r"\d"
    fmt = "01d"
    contains = ("month", "day")
    description = "Week day (1-7, Monday=1)"


class DateElementU(DateElementStrInt):
    """Week number, starting from first Sunday."""

    key = "U"
    regex = r"\d\d"
    fmt = "02d"
    contains = ("month", "day")
    description = "Week number (00-53, week 1 starts at first Sunday)"


class DateElementw(DateElementStrInt):
    """Weekday (0-6, Sunday=0)."""

    key = "w"
    regex = r"\d"
    fmt = "01d"
    contains = ("month", "day")
    description = "Week day (1-7, Sunday=0)"


class DateElementW(DateElementStrInt):
    """Week number, starting from first Monday."""

    key = "W"
    regex = r"\d\d"
    fmt = "02d"
    contains = ("month", "day")
    description = "Week number (00-53, week 1 starts at first Monday)"


## Others
class DateElementp(DateElement):
    """AM/PM."""

    key = "p"
    regex = r"AM|PM"
    contains = ("hour",)
    description = "AM/PM"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        if not isinstance(date, dt.datetime):
            raise TypeError
        return "AM" if date.hour < 12 else "PM"


class DateElementP(DateElement):
    """am/pm."""

    key = "P"
    regex = r"am|pm"
    contains = ("hour",)
    description = "am/pm"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        if not isinstance(date, dt.datetime):
            raise TypeError
        return "am" if date.hour < 12 else "pm"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: ARG002
        return {"p": s.upper()}


class DateElements(DateElement):
    """Timestamp (seconds since epoch)."""

    key = "s"
    regex = r"[+-]?\d+(?:\.\d{6})?"
    fmt = ".6f"
    contains = ("year", "month", "day", "hour", "minute", "second", "microsecond")
    description = "Timestamp, seconds since epoch (1970-01-01 00:00:00 UTC)"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> float:
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
    description = "UTC offset (±HHMM[SS[.ffffff]])"

    def format(self, value: str | dt.tzinfo) -> str:
        if isinstance(value, dt.tzinfo):
            # this allows for passing a timezone object in the default date
            return self.datetime_to_value(dt.datetime(1970, 0, 0, tzinfo=value))
        return super().format(value)

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        if not isinstance(date, dt.datetime):
            raise TypeError
        return date.strftime("%z") if date.tzinfo is not None else "+0000"


## Composites
class DateElementF(DateElement):
    """Date (YYYY-mm-dd). Not locale dependant."""

    key = "F"
    regex = r"\d{4}-\d\d-\d\d"
    contains = ("year", "month", "day")
    description = "Date (YYYY-mm-dd)"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        return f"{date.year:04d}-{date.month:02d}-{date.day:02d}"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: ARG002
        splits = s.split("-")
        if len(splits) != 3:
            raise ValueError(f"Could not parse date '{s}' (expected YYYY-mm-dd).")

        return dict(zip(["Y", "m", "d"], splits, strict=True))


class DateElementx(DateElement):
    """Date (YYYYmmdd). Not locale dependant."""

    key = "x"
    regex = r"\d{8}"
    contains = ("year", "month", "day")
    description = "Date (YYYYmmdd)"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        return f"{date.year:04d}{date.month:02d}{date.day:02d}"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: ARG002
        if len(s) < 5:
            raise ValueError(f"Could not parse date '{s}' (expected YYYYmmdd).")
        return {"Y": s[:-4], "m": s[-4:-2], "d": s[-2:]}


class DateElementT(DateElement):
    """Time (HHMMSS). Not locale dependant."""

    key = "T"
    regex = r"\d{6}"
    contains = ("hour", "minute", "second")
    description = "Time (HHMMSS)"

    def datetime_to_value(self, date: dt.datetime | dt.date) -> str:
        if not isinstance(date, dt.datetime):
            raise TypeError
        return f"{date.hour:02d}{date.minute:02d}{date.second:02d}"

    def prepare(self, s: str, **kwargs: Any) -> dict[str, str]:  # noqa: ARG002
        if len(s) != 6:
            raise ValueError(f"Could not parse time '{s}' (expected HHMMSS).")
        return {"H": s[:2], "M": s[2:4], "S": s[4:]}


def datetime_to_str(date: dt.datetime | dt.date, element: str) -> str:
    """Extract element from a datetime object and format it."""
    return DateElement.get(element).datetime_to_str(date)


def datetime_to_value(date: dt.datetime | dt.date, element: str) -> int | float | str:
    """Extract element from a datetime object."""
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

    Use with::

        date = DateParser(matches, default_date).parse()

    Parameters
    ----------
    matches:
        Matches obtained from a filename, corresponding to date elements. The
        :attr:`.Group.date_element` attribute must be defined.
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
            elt_obj = m.group.date_element
            if elt_obj is None:
                raise ValueError(f"'{m.group}' is not a date group.")
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
