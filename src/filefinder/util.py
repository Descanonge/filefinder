"""General utilities."""

import typing as t
from collections import abc

if t.TYPE_CHECKING:
    from .group import Group, GroupKey


class Sentinel:
    """Sentinel objects."""

    def __init__(self, msg: str = ""):
        self.msg = msg

    def __str__(self) -> str:
        return self.msg


def get_groups_indices(groups: list[Group], key: GroupKey) -> list[int]:
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
