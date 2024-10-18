"""Functions to retrieve values from filename."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import datetime as dt
import logging
from collections import abc

from .finder import Finder
from .matches import Match, Matches
from .util import date_from_doy, name_to_date

logger = logging.getLogger(__name__)


def get_date(
    matches: Matches, default_date: abc.Mapping[str, int] | None = None
) -> dt.datetime:
    """Retrieve date from matched elements.

    Matches that can be used are : YBmdjHMSFxX. If a matcher is *not* found in the
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

    def process(key: str, callback: abc.Callable[[Match], dict[str, int]]):
        """Run *callback* on matches selected by *key*.

        The callback returns a dictionnary with the datetime arguments (elements) it
        found. Each new value is added to the list of values found for that element.
        """
        for m in matches:
            if m.group.name != key or m.group.discard:
                continue
            for elt, val in callback(m).items():
                if elt not in elts:
                    elts[elt] = []
                elts[elt].append(val)

    def process_B(m: Match):
        return dict(month=_find_month_number(m.match_str))

    def process_F(m: Match):
        # YYYY-mm-dd
        # 0123456789
        value = m.match_str
        out = dict(year=value[:4], month=value[5:7], day=value[8:10])
        return {elt: int(val) for elt, val in out.items()}

    def process_x(m: Match):
        # YYYYmmdd
        # 012345678
        value = m.match_str
        out = dict(year=value[:4], month=value[4:6], day=value[6:8])
        return {elt: int(val) for elt, val in out.items()}

    def process_X(m: Match):
        # HHMMSS (seconds optional)
        # 0123456
        value = m.match_str
        out = dict(hour=value[:2], minute=value[2:4])
        if len(value) > 4:
            out["second"] = value[4:6]
        return {elt: int(val) for elt, val in out.items()}

    def process_j(m: Match):
        doy = m.get_match(parse=True)
        # This depend on the value of year, we take the first one discovered, or from
        # the default one if none was processed yet
        if "year" in elts:
            year = elts["year"][0]
        else:
            year = default_date["year"]
        return date_from_doy(doy, year)

    def process_simple(m: Match):
        value = m.get_match(parse=True)
        elts = name_to_date[m.group.name]
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
        logger.warning("No date elements could be recovered. Returning default date.")

    for elt, values in elts.items():
        if any(v != values[0] for v in values):
            raise ValueError(f"Different values found for {elt}: {values}")

    date = default_date
    for elt, values in elts.items():
        date[elt] = values[0]

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
