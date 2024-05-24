"""Functions to retrieve values from filename."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import datetime as dt
import logging
from collections.abc import Callable

from .finder import Finder
from .matches import Matches

logger = logging.getLogger(__name__)


def get_date(matches: Matches, default_date: dict | None = None) -> dt.datetime:
    """Retrieve date from matched elements.

    If a matcher is *not* found in the filename, it will be replaced by the
    element of the default date argument.
    Matchers that can be used are (in order of increasing priority):
    YBmdjHMSFxX. If two matchers have the same name, the last one in the
    pre-regex will get priority.

    Parameters
    ----------
    matches:
        Matches obtained from a filename.
    default_date:
        Default date. Dictionnary with keys: year, month, day, hour, minute,
        and second. Defaults to 1970-01-01 00:00:00
    """
    name_to_datetime = dict(
        Y="year", m="month", d="day", H="hour", M="minute", S="second"
    )

    def get_elts(elts: dict[str, str], names: str, callback: Callable):
        for name in names:
            elt = elts.pop(name, None)
            if elt is not None:
                date.update(callback(elt, name))

    def process_int(elt: str, name: str) -> dict[str, int]:
        return {name_to_datetime[name]: int(elt)}

    def process_month_name(elt: str, name: str) -> dict[str, int]:
        return dict(month=_find_month_number(elt))

    def process_doy(elt: str, name: str) -> dict[str, int]:
        d = dt.datetime(date["year"], 1, 1) + dt.timedelta(days=int(elt) - 1)
        return dict(month=d.month, day=d.day)

    date = {"year": 1970, "month": 1, "day": 1, "hour": 0, "minute": 0, "second": 0}

    if default_date is None:
        default_date = {}
    date.update(default_date)

    elts = {
        m.group.name: m.get_match(parse=False) for m in matches if not m.group.discard
    }

    elts_needed = set("xXYmdBjHMSF")
    if len(set(elts.keys()) & elts_needed) == 0:
        logger.warning(
            "No matchers to retrieve a date from." " Returning default date."
        )

    # Process month name first to keep element priorities simples
    get_elts(elts, "B", process_month_name)

    # Decompose elements
    elt = elts.pop("F", None)
    if elt is not None:
        elts["Y"] = elt[:4]
        elts["m"] = elt[5:7]
        elts["d"] = elt[8:10]

    elt = elts.pop("x", None)
    if elt is not None:
        elts["Y"] = elt[:4]
        elts["m"] = elt[4:6]
        elts["d"] = elt[6:8]

    elt = elts.pop("X", None)
    if elt is not None:
        elts["H"] = elt[:2]
        elts["M"] = elt[2:4]
        if len(elt) > 4:  # noqa: PLR2004
            elts["S"] = elt[4:6]

    # Process elements
    get_elts(elts, "Ymd", process_int)
    get_elts(elts, "j", process_doy)
    get_elts(elts, "HMS", process_int)

    return dt.datetime(**date)  # type: ignore


def _find_month_number(name: str) -> int:
    """Find a month number from its name.

    Name can be the full name (January) or its three letter abbreviation (jan).
    The casing does not matter.
    """
    names = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december",
    ]
    names_abbr = [c[:3] for c in names]

    name = name.lower()
    if name in names:
        return names.index(name) + 1
    if name in names_abbr:
        return names_abbr.index(name) + 1

    raise ValueError(f"Could not interpret month name '{name}'")


def filter_by_range(
    finder: Finder,
    filename: str,
    matches: Matches,
    group: str,
    min: float | None = None,
    max: float | None = None,
) -> bool:
    """Filter filename using the value parsed for `group`.

    Keep filename for which the value parsed for `group` fall within a specific range
    defined by `min` and `max`.

    Parameters
    ----------
    group
        Name of the group to use the parsed value. The first non-discard group of that
        name will be used.
    min
        If not None, the parsed value must be above this.
    max
        If not None, the parsed value mest be below this.

    Raises
    ------
    TypeError
        `min` and `max` cannot be both None.
    """
    if min is None and max is None:
        raise TypeError("`min` and `max` cannot be both None.")

    parsed = matches.get_value(group, parse=True, keep_discard=False)

    if min is not None and parsed < min:
        return False
    if max is not None and parsed > max:
        return False
    return True


def filter_date_range(
    finder: Finder,
    filename: str,
    matches: Matches,
    start: dt.date | str,
    stop: dt.date | str,
    default_date: dict | None = None,
) -> bool:
    """Filter filename to be between two dates.

    Parameters
    ----------
    start, stop
        Start and stop dates that define the range of dates to keep. Can each be a
        :class:`datetime.date` or :class:`datetime.datetime` object; or a string in
        which case a datetime object is created with
        :meth:`~datetime.datetime.fromisoformat`.
    default_date
        Is passed to :func:`get_date`.

    Returns
    -------
    keep
        True if the file is within the range and must be kept. False otherwise.
    """
    if isinstance(start, str):
        start = dt.datetime.fromisoformat(start)
    if isinstance(stop, str):
        stop = dt.datetime.fromisoformat(stop)

    if start >= stop:
        raise ValueError(f"Start ({start}) must be before stop ({stop})")

    current = get_date(matches, default_date=default_date)

    return start <= current <= stop
