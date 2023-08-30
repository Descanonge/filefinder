"""Functions to retrieve values from filename."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import logging
from collections.abc import Callable
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from .finder import Finder
from .matches import Matches

if TYPE_CHECKING:
    import xarray

logger = logging.getLogger(__name__)


def get_date(matches: Matches,
             default_date: dict | None = None,
             groups: list[str] | None = None) -> datetime:
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
    groups:
        If not None, restrict matches for the groups which names are in this
        list.
    default_date:
        Default date. Dictionnary with keys: year, month, day, hour, minute,
        and second. Defaults to 1970-01-01 00:00:00
    """
    name_to_datetime = dict(
        Y='year', m='month', d='day', H='hour', M='minute', S='second')

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
        d = datetime(date['year'], 1, 1) + timedelta(days=int(elt)-1)
        return dict(month=d.month, day=d.day)

    date = {'year': 1970, 'month': 1, 'day': 1,
            'hour': 0, 'minute': 0, 'second': 0}

    if default_date is None:
        default_date = {}
    date.update(default_date)

    elts = {m.group.name: m.get_match(parse=False)
            for m in matches
            if (not m.group.discard
                and (groups is None or m.group.name in groups))}

    elts_needed = set('xXYmdBjHMSF')
    if len(set(elts.keys()) & elts_needed) == 0:
        logger.warning('No matchers to retrieve a date from.'
                       ' Returning default date.')

    # Process month name first to keep element priorities simples
    get_elts(elts, 'B', process_month_name)

    # Decompose elements
    elt = elts.pop('F', None)
    if elt is not None:
        elts['Y'] = elt[:4]
        elts['m'] = elt[5:7]
        elts['d'] = elt[8:10]

    elt = elts.pop('x', None)
    if elt is not None:
        elts['Y'] = elt[:4]
        elts['m'] = elt[4:6]
        elts['d'] = elt[6:8]

    elt = elts.pop('X', None)
    if elt is not None:
        elts['H'] = elt[:2]
        elts['M'] = elt[2:4]
        if len(elt) > 4:  # noqa: PLR2004
            elts['S'] = elt[4:6]

    # Process elements
    get_elts(elts, 'Ymd', process_int)
    get_elts(elts, 'j', process_doy)
    get_elts(elts, 'HMS', process_int)

    return datetime(**date) # type: ignore


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

    raise ValueError(f"Could not interpret month name '{name}'")


def get_func_process_filename(
        finder: Finder,
        func: Callable[..., 'xarray.Dataset'],
        relative: bool = True,
        *args, **kwargs) -> Callable[['xarray.Dataset'], 'xarray.Dataset']:
    r"""Get a function that can preprocess a dataset.

    Written to be used as the 'process' argument of
    `xarray.open_mfdataset`. Allows to use a function with additional
    arguments, that can retrieve information from the filename.

    Parameters
    ----------
    func:
        Input arguments are (`xarray.Dataset`, filename: `str`,
        `Finder`, \*args, \*\*kwargs).
        Should return a Dataset.
        The filename is retrieved from the dataset encoding attribute.
    relative:
        If True (default), `filename` is made relative to the finder root. This
        is necessary to match the filename against the finder regex.
    args:
        Passed to `func` when called.
    kwargs:
        Passed to `func` when called.

    Returns
    -------
    preprocess
            Function with signature suitable for :func:`xarray.open_mfdataset`.

    Examples
    --------
    This retrieve the date from the filename, and add a time dimensions
    to the dataset with the corresponding value.
    >>> from filefinder import library
    ... def process(ds, filename, finder, default_date=None):
    ...     matches = finder.find_matches(filename)
    ...     date = library.get_date(matches, default_date=default_date)
    ...     ds = ds.assign_coords(time=[date])
    ...     return ds
    ...
    ... ds = xr.open_mfdataset(
    ...     finder.get_files(),
    ...     preprocess=get_func_process_filename(
    ...         finder, process, default_date={'hour': 12}))
    """
    def f(ds):
        filename = ds.encoding['source']
        if relative:
            filename = finder.get_relative(filename)
        return func(ds, filename, finder, *args, **kwargs)
    return f
