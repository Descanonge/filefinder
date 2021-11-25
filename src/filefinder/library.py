"""Functions to retrieve values from filename."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

from datetime import datetime, timedelta
import logging
from typing import Dict

from filefinder.matcher import Matches

log = logging.getLogger(__name__)


def get_date(matches: Matches, default_date: Dict = None,
             group: str = None) -> datetime:
    """Retrieve date from matched elements.

    If a matcher is *not* found in the filename, it will be replaced by the
    element of the default date argument.
    Matchers that can be used are (in order of increasing priority):
    YBmdjHMSFxX. If two matchers have the same name, the last one in the
    pre-regex will get priority.

    Parameters
    ----------
    matches: :class:`Matches<filefinder.matcher.Matches>`
        Matches obtained from a filename.
    group: str
        If not None, restrict matchers to this group.
    default_date: dict, optional
        Default date. Dictionnary with keys: year, month, day, hour, minute,
        and second. Defaults to 1970-01-01 00:00:00

    Raises
    ------
    KeyError
        If no matchers are found to create a date from.
    """
    NAME_TO_DATETIME = dict(
        Y='year', m='month', d='day', H='hour', M='minute', S='second')

    def get_elts(names: str, callback):
        for name in names:
            elt = elts.pop(name, None)
            if elt is not None:
                date.update(callback(elt, name))

    def process_int(elt, name):
        return {NAME_TO_DATETIME[name]: int(elt)}

    def process_month_name(elt, name):
        elt = _find_month_number(elt)
        if elt is not None:
            return dict(month=elt)
        return {}

    def process_doy(elt, name):
        elt = datetime(date["year"], 1, 1) + timedelta(days=int(elt)-1)
        return dict(month=elt.month, day=elt.day)

    date = {"year": 1970, "month": 1, "day": 1,
            "hour": 0, "minute": 0, "second": 0}

    if default_date is None:
        default_date = {}
    date.update(default_date)

    elts = {m.matcher.name: m.get_match(parsed=False) for m in matches
            if (not m.matcher.discard
                and (group is None or m.matcher.group == group))}

    elts_needed = set('xXYmdBjHMSF')
    if len(set(elts.keys()) & elts_needed) == 0:
        log.warning("No matchers to retrieve a date from."
                    " Returning default date.")

    # Process month name first to keep element priorities simples
    get_elts('B', process_month_name)

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
        if len(elt) > 4:
            elts["S"] = elt[4:6]

    # Process elements
    get_elts('Ymd', process_int)
    get_elts('j', process_doy)
    get_elts('HMS', process_int)

    return datetime(**date)


def _find_month_number(name: str) -> int:
    """Find a month number from its name.

    Name can be the full name (January) or its three letter abbreviation (jan).
    The casing does not matter.
    """
    names = ['january', 'february', 'march', 'april',
             'may', 'june', 'july', 'august', 'september',
             'october', 'november', 'december']
    names_abbr = [c[:3] for c in names]

    name = name.lower()
    if name in names:
        return names.index(name) + 1
    if name in names_abbr:
        return names_abbr.index(name) + 1

    return None
