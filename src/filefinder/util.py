"""General utilities."""

from datetime import date, datetime, timedelta

from .group import Group, GroupKey

datetime_keys = "YBmdjHMSFxX"

name_to_date = {
    "F": ["year", "month", "day"],
    "x": ["year", "month", "day"],
    "X": ["hour", "minute", "second"],
    "Y": ["year"],
    "m": ["month"],
    "B": ["month"],
    "d": ["day"],
    "j": ["month", "day"],
    "H": ["hour"],
    "M": ["minute"],
    "S": ["second"],
}
"""Elements of datetime to set for each group."""


def datetime_to_str(date: datetime, name: str) -> str:
    """Return formatted string  of a date group name (Y, m, d, ...)."""
    if name in "mdHMS":
        elt = name_to_date[name][0]
        return f"{getattr(date, elt):02d}"
    if name == "Y":
        return f"{date.year:04d}"
    if name == "j":
        doy = get_doy(date)
        return f"{doy:03d}"
    if name == "F":
        return f"{date.year:04}-{date.month:02d}-{date.day:02d}"
    if name == "x":
        return f"{date.year:04}{date.month:02d}{date.day:02d}"
    if name == "X":
        return f"{date.hour:02}{date.minute:02d}{date.second:02d}"
    if name == "B":
        return date.strftime("%B")

    raise KeyError(f"Element '{name}' not supported [{datetime_keys}]")


def datetime_to_value(date: datetime, name: str) -> int | str:
    """Return value of date group name (Y, m, F, ...)."""
    if name == "j":
        return get_doy(date)

    if name in "xXFB":
        return datetime_to_str(date, name)

    elt = name_to_date[name]
    assert len(elt) == 1
    return getattr(date, elt[0])


def get_doy(date: datetime) -> int:
    """Return dayofyear of a date."""
    return (date - datetime(date.year, 1, 1)).days + 1


def date_from_doy(doy: int, year: int) -> dict[str, int]:
    """Get month and day from a dayofyear value (and its year)."""
    day = date(year, 1, 1) + timedelta(days=(doy - 1))
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
    IndexError: No group found corresponding to the key
    TypeError: Key is not int or str
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
