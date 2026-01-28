"""General utilities."""

import datetime as dt

from .group import Group, GroupKey

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


def _check_input(date: dt.datetime | dt.date, name: str):
    if name in time_keys and not isinstance(date, dt.datetime):
        raise TypeError(
            f"'{name}' group needs time information "
            f"(received a {type(date)} object)"
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
    """Return value of date group name (Y, m, F, ...)."""
    _check_input(date, name)

    if name == "j":
        return get_doy(date)

    if name in "xXFB":
        s = datetime_to_str(date, name)
        # xX can be returned as int, as per their format in DEFAULT_GROUPS
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
    return dict(month=day.month, day=day.day)


class Sentinel:
    """Sentinel objects."""

    def __init__(self, msg: str = ""):
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


def get_groups_indices(
    groups: list[Group], key: GroupKey, date_is_first_class: bool = True
) -> list[int]:
    """Get sorted list of groups indices corresponding to key.

    Key can be an integer index, or a string of a group name. Since multiple
    groups can share the same name, multiple indices can be returned (sorted).

    Raises
    ------
    IndexError
        No group found corresponding to the key
    TypeError
        Key is not int or str
    """
    if isinstance(key, int):
        return [key]
    if isinstance(key, str):
        if key == "date" and date_is_first_class:
            selected = [
                i for i, group in enumerate(groups) if group.name in datetime_keys
            ]
        else:
            selected = [i for i, group in enumerate(groups) if group.name == key]

        if len(selected) == 0:
            raise IndexError(f"No group found for key '{key}'")
        return selected

    raise TypeError("Key must be int or str.")
