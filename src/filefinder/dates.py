"""Date related utilities."""

from __future__ import annotations

import calendar
import datetime as dt
import re
from collections.abc import Callable, Mapping, Sequence
from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from .matches import GroupMatch

DefaultDate = dt.datetime | dt.date | Mapping[str, int]
"""Type for default_date argument."""

DATETIME_ELEMENTS = "aAbBdfFHIjmMpPsSTuUxwWYz"
TIME_ELEMENTS = "HIMpPsSTz"
STRING_ELEMENTS = "aAbBFpPTxz"


def _has_any_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) > 0


def _has_all_keys(d: Mapping, keys: Sequence) -> bool:
    return len(set(keys) & d.keys()) == len(keys)


_datetime_args = [
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "second",
    "microsecond",
    "tzinfo",
]


def _datetime_to_dict(date: dt.datetime) -> dict:
    return {attr: getattr(date, attr) for attr in _datetime_args}


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

    if element == "x":
        return date.strftime("%Y%m%d")

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

    Matches that can be used are in :attr:`DATETIME_ELEMENTS`. They are used to find the
    arguments to pass to :class:`datetime.datetime`. If the matches do not permit to
    recover all arguments, missing arguments will be taken from the `default_date`.
    Missing elements will also been taken from the default date when necessary to parse,
    for instance, to account for leap years ``%(j)`` will need the year to find the
    month and day: it will use the parsed year if present in the matches, or the year of
    the default date otherwise.

    If multiple matches yield different values for the same argument (for instance if
    the group Y and F give a different year), an exception will be raised.

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
      supply the missing information with keys ``weekday`` (equivalent to ``%w``) or
      ``weeknumber`` (equivalent to ``%W``).

    Similarly, when parsing the hour from a 12-hour clock, the parser will need element
    ``I`` and either ``p`` or ``P``, otherwise an exception will be raised.

    Some of the parsing (especially week number/day) is relying on
    :meth:`~datetime.datetime.strptime`, whose availability may be platform dependent
    (see :ref:`strftime-strptime-behavior`). Parsing the timestamp is also subject to
    some limitations, computation may not be accurate to the microsecond when years are
    too far from the epoch (see :meth:`~datetime.datetime.fromtimestamp`).

    The names of months and week days are those of the current locale.

    Use with either::

        date = DateParser.parse(matches, default_date)

        # or

        parser = DateParser(matches, default_date)
        date = parser.retrieve_date()

    Parameters
    ----------
    matches:
        Matches obtained from a filename.
    default_date:
        If an element is not found in the filename, use the element from this default
        date. It can be a :mod:`datetime` object or a mapping with keys among: year,
        month, day, hour, minute, second, microsecond, tzinfo. Missing elements will
        default to 1970-01-01 00:00:00 (naive). One can also supply ``weekday``
        (equivalent to ``%w``) or ``weeknumber`` (equivalent to ``%W``) to give missing
        week day/number information.
    """

    DEFAULT_DATE_DEFAULT: ClassVar[dict] = {
        "year": 1970,
        "month": 1,
        "day": 1,
        "hour": 0,
        "minute": 0,
        "second": 0,
        "microsecond": 0,
        "tzinfo": None,
    }
    """Default values for the default_date. Note it is offset-naive."""

    PROCESS_ORDER: ClassVar[dict[str, str]] = {
        "z": "z",
        "s": "s",
        "Ymd": "basic",
        "b": "b",
        "B": "B",
        "F": "F",
        "x": "x",
        "j": "j",
        "aAuUwW": "week_day",
        "T": "T",
        "HMSf": "basic",
        "IpP": "hour_12",
    }
    """Processing methods for various elements, in order they are to be processed.

    If the matches contain any of the elements in the key, the value will indicate the
    method to use.
    """

    def __init__(
        self, matches: Sequence[GroupMatch], default_date: DefaultDate | None = None
    ) -> None:
        self.matches: list[GroupMatch] = list(matches)

        if default_date is None:
            default_date = {}
        if isinstance(default_date, dt.datetime):
            default_date = _datetime_to_dict(default_date)
        elif isinstance(default_date, dt.date):
            default_date = {
                attr: getattr(default_date, attr) for attr in ["year", "month", "day"]
            }

        self.default_args = self.DEFAULT_DATE_DEFAULT | dict(default_date)
        """Default datetime arguments.

        Used if an element is missing from the matches. Contains elements:
        year, month, day, hour, minute, second, microsecond, tzinfo, and eventually
        weeknumber or weekday.
        """

        self.elements: dict[str, str] = self.matches_to_elements()
        """Dictionary of elements names to matched strings."""
        self.date_args_all: dict[str, dict[str, int | float | dt.timezone]] = {}
        """Parsed datetime arguments from all elements.

        Store as ``{argument_name: {source_element(s): value}}``. For instance
        ``{"second": {"s": 32, "S": 32}, ...}``. This allows to check that different
        elements are parsed as the same datetime arguments.
        """

    @classmethod
    def parse(
        cls, matches: Sequence[GroupMatch], default_date: DefaultDate | None = None
    ) -> dt.datetime:
        """Retrieve a date from matches."""
        parser = cls(matches, default_date)
        return parser.retrieve_date()

    @property
    def date_args(self) -> dict[str, int | float | dt.timezone]:
        """Arguments to pass to :class:`datetime.datetime`."""
        date_args = {}
        for arg_name, from_names in self.date_args_all.items():
            names = list(from_names.keys())
            date_args[arg_name] = from_names[names[0]]
        return date_args

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

    def retrieve_date(self) -> dt.datetime:
        """Retrieve a date from matches.

        The main parsing function.
        """
        self.elements = self.matches_to_elements()
        self.date_args_all = {}

        for element_names, method_name in self.PROCESS_ORDER.items():
            method = getattr(self, f"process_{method_name}")
            self.process(element_names, method)

        return self.create_date()

    def process(self, names: str, callback: Callable[..., dict]) -> None:
        """Process elements using a given method.

        If matches have any elements from `names`, launch the callback. The callback
        must be a bound method that takes no arguments (other than `self`). It should
        process the elements and return a dictionary of arguments for
        :class:`datetime.datetime`.

        The result of the callback is added to :attr:`.date_args_all` and if some
        argument is different from what a previous callback processed, an exception is
        raised.
        """
        if _has_any_keys(self.elements, names):
            date_args = callback()
            for k, v in date_args.items():
                if k not in self.date_args_all:
                    self.date_args_all[k] = {names: v}
                else:
                    self.date_args_all[k][names] = v

                if any(v != old for old in self.date_args_all[k].values()):
                    raise ValueError(
                        f"Parsed different values for '{k}' in different groups. "
                        f"Found {self.date_args_all[k]}."
                    )

    def get(self, arg: str) -> int | float | dt.timezone | None:
        """Return the corresponding parsed argument.

        If the argument has been parsed, return that value. If not, return its value
        from the `default_date`. If not present, raise an exception.
        """
        if arg in self.date_args_all:
            return self.date_args[arg]
        if arg in self.default_args:
            return self.default_args[arg]
        raise KeyError(
            f"Argument '{arg}' is neither in current parsed arguments nor in "
            "default arguments."
        )

    def create_date(self) -> dt.datetime:
        """Create a datetime object from parsed arguments."""
        args = dict(self.default_args)
        args.pop("weeknumber", None)
        args.pop("weekday", None)
        for k in args:
            if k not in _datetime_args:
                raise TypeError(
                    f"Unrecognized argument '{k}' for datetime.datetime. "
                    "Check default_date parameter."
                )
        args |= self.date_args
        return dt.datetime(**args)  # type: ignore[arg-type]

    def process_z(self) -> dict[str, dt.timezone]:
        """Process timezone information.

        **Elements:** ``z``

        ``z`` should be of the form ±HHMM[SS.[ffffff]].

        Returns
        -------
        arguments:
            The `tzinfo` key.
        """
        m = re.fullmatch(
            r"([+-])(\d\d)(\d\d)(?:(\d\d)(?:\.(\d{6}))?)?", self.elements["z"]
        )
        if m is None:
            raise ValueError(
                f"Could not parse timezone information '{self.elements['z']}' "
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

        tz = dt.timezone(delta)
        return {"tzinfo": tz}

    def process_s(self) -> dict[str, int | float]:
        """Process timestamp.

        **Elements:** ``s``.

        Timezone information should have been parsed already.

        Returns
        -------
        arguments:
            All arguments. `tzinfo` only present if timezone information was available
            in matches or default date.
        """
        tz = self.get("tzinfo")
        is_naive = tz is None
        if is_naive:
            tz = dt.UTC  # otherwise fromtimestamp assumes local time

        date = dt.datetime.fromtimestamp(float(self.elements["s"]), tz=tz)  # type: ignore[arg-type]

        args = _datetime_to_dict(date)
        if is_naive:
            args.pop("tzinfo")
        return args

    def process_basic(self) -> dict[str, int]:
        """Process simple elements.

        **Elements:** ``Y, m, d, H, M, S, f``

        Returns
        -------
        arguments:
            Any and all corresponding arguments.
        """
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
        """Process month name.

        **Elements:** ``B``

        Uses :attr:`calendar.month_name` (current locale). Could be changed so that a
        specific locale could be used. This is not casing dependent.

        Returns
        -------
        arguments:
            The `month` key.

        Raises
        ------
        KeyError
            Unrecognised month name.
        """
        name = self.elements.pop("B").lower()
        names = [m.lower() for m in calendar.month_name]
        if name in names:
            return {"month": names.index(name)}

        raise KeyError(
            f"Month name '{name}' unrecognised. Must be a name from the "
            f"current locale, among {names[1:]} (not case dependent)."
        )

    def process_b(self) -> dict[str, int]:
        """Process abbreviated month name.

        **Elements:** ``b``

        Uses :attr:`calendar.month_abbr` (current locale). Could be changed so that a
        specific locale could be used. This is not casing dependent.

        Returns
        -------
        arguments:
            The `month` key.

        Raises
        ------
        KeyError
            Unrecognised month abbreviation.
        """
        name = self.elements.pop("b").lower()
        names = [m.lower() for m in calendar.month_abbr]
        if name in names:
            return {"month": names.index(name)}

        raise KeyError(
            f"Abbreviated month name '{name}' unrecognised. Must be a name from the "
            f"current locale, among {names[1:]} (not case dependent)."
        )

    def process_F(self) -> dict[str, int]:  # noqa: N802
        """Process match for full date (YYYY-mm-dd).

        **Elements**: ``F``

        Returns
        -------
        arguments:
            Keys `year`, `month`, and `day`.
        """
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
        """Process match for full date (YYYYmmdd).

        **Elements:** ``x``

        This departs from ISO as the year does not have to be padded with 0.

        Returns
        -------
        arguments:
            Keys `year`, `month`, and `day`.
        """
        s = self.elements["x"]
        if len(s) < 5:
            raise ValueError(f"Could not parse date '{s}' (expected YYYYmmdd).")
        out = {"year": s[:-4], "month": s[-4:-2], "day": s[-2:]}
        return {elt: int(val) for elt, val in out.items()}

    def process_T(self) -> dict[str, int]:  # noqa: N802
        """Process match for time (HHMMSS).

        **Elements:** ``T``

        Returns
        -------
        arguments:
            Keys `hour`, `minute`, and `second`.
        """
        s = self.elements["T"]
        if len(s) != 6:
            raise ValueError(f"Could not parse time '{s}' (expected HHMMSS).")
        out = {"hour": s[:2], "minute": s[2:4], "second": s[4:6]}
        return {elt: int(val) for elt, val in out.items()}

    def process_j(self) -> dict[str, int]:
        """Process day of the year (j).

        **Elements:** ``j``

        Needs the year to have been parsed.

        Returns
        -------
        arguments:
            Keys `month` and `day`.
        """
        s = self.elements["j"]
        date = dt.date(self.get("year"), 1, 1) + dt.timedelta(days=int(s) - 1)  # type: ignore[arg-type]
        return {"month": date.month, "day": date.day}

    def process_hour_12(self) -> dict[str, int]:
        """Process hour as a 12-hour clock (IpP).

        **Elements:** ``IpP``

        If not both ``I`` and either ``p`` or ``P`` elements are present, an exception
        will be raised.

        Result
        ------
        arguments:
            The key `hour`.
        """
        present = {c for c in self.elements if c in "IpP"}
        has_p = "p" in present or "P" in present
        has_i = "I" in present
        if has_p != has_i:
            raise ValueError(
                "Need both %I (12-hour clock) and %p/%P (am/pm) to retrieve hour"
                f"received {present}."
            )

        ampm = self.elements.get("p") or self.elements["P"]

        hour = int(self.elements["I"]) % 12
        if ampm.lower() == "pm":
            hour += 12
        return {"hour": hour}

    def process_week_day(self) -> dict[str, int]:
        """Process the week day and week number. (aAuwUW).

        **Elements:** ``aAuwUW``

        Needs the year to be parsed. Needs both information about day of week and week
        number. If one of them is missing:

        - If month/day information has already been parsed, return an empty dict.
        - If missing information is not present in default date, raise.

        This relies on :meth:`datetime.datetime.strptime`, availability of element ``u``
        may be platform dependent.

        Returns
        -------
        arguments:
            Keys `month` and `day`, or empty dict.
        """
        values = {c: self.elements[c] for c in "aAuwUW" if c in self.elements}

        def can_process(
            elements_missing: str, default_equivalent: str, present: str, missing: str
        ) -> bool:
            if not _has_any_keys(values, elements_missing):
                # we are missing weekday or weeknumber
                if _has_all_keys(self.date_args_all, ["month", "day"]):
                    # we have other group that found the date
                    # we can ignore week day/number
                    return False
                if missing not in self.default_args:
                    raise ValueError(
                        f"Cannot determine date with only {present} and not {missing} "
                        f"(only received elements {list(values.keys())}). Other groups "
                        "do not have month/day information: parsing will fallback to "
                        f"the default date. You may indicate the default {missing} with "
                        f"``default_date={{'{missing}': ...}}``, "
                        f"equivalent to %{default_equivalent}."
                    )
                    return False
                values[default_equivalent] = str(self.default_args[missing])
            return True

        if not can_process(
            elements_missing="aAuw",
            default_equivalent="w",
            present="weeknumber",
            missing="weekday",
        ):
            return {}
        if not can_process(
            elements_missing="UW",
            default_equivalent="W",
            present="weekday",
            missing="weeknumber",
        ):
            return {}

        fmt = "%Y_" + "_".join(f"%{c}" for c in values)
        date_string = f"{self.get('year'):04d}" + "_" + "_".join(values.values())

        date = dt.datetime.strptime(date_string, fmt)
        return {"month": date.month, "day": date.day}
