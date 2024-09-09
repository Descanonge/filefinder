"""General utilities."""

from collections import abc
from datetime import datetime

from .group import Group, GroupKey

datetime_keys = "YBmdjHMSFxX"


def datetime_to_str(date: datetime, elt: str) -> str:
    """Return string of formatted element *elt*.

    *elt* must be in :attr:`datetime_keys`.
    """
    if elt not in datetime_keys:
        raise KeyError(f"Element '{elt}' not supported [{datetime_keys}]")

    if elt == "x":
        fmt = "%Y%m%d"
    elif elt == "X":
        fmt = "%H%M%S"
    elif elt == "F":
        fmt = "%Y-%m-%d"
    else:
        fmt = f"%{elt}"

    return date.strftime(fmt)


def datetime_to_value(date: datetime, elt: str) -> int | str:
    """Return value of element *elt*."""
    # needed because I don't have access to dayofyear
    formatted = datetime_to_str(date, elt)

    if elt in "xXFB":
        return formatted
    return int(formatted)


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


def get_unique_name(name: str, existing: abc.Container[str]) -> str:
    """Return string starting with *name* and not contained in *existing*."""
    i = 0
    r_name = f"{name}__{i}"
    while r_name in existing:
        i += 1
        r_name = f"{name}__{i}"
    return r_name
