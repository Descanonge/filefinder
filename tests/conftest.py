import os
from os import path

from hypothesis import HealthCheck, Verbosity, settings
from pytest import Config, Item, PytestCollectionWarning, Session

settings.register_profile(
    "ci", max_examples=1000, suppress_health_check=[HealthCheck.too_slow]
)
settings.register_profile("dev", max_examples=50)
settings.register_profile("debug", max_examples=50, verbosity=Verbosity.verbose)

settings.load_profile(os.getenv("HYPOTHESIS_PROFILE", "dev").lower())


def pytest_collection_modifyitems(
    session: Session, config: Config, items: list[Item]
) -> None:
    """Pytest hook.

    Called after collection has been performed. Items are re-ordered in place to
    be sorted not alphabetically but by module (test_format, then group, finder,
    and library), and by line number inside each module.
    """
    # test modules in order to be tested, relative to the root config (normally here)
    module_order = [
        path.join("tests", "unit", f"test_{s}.py")
        for s in ["format", "group", "filters", "finder", "library"]
    ]

    items_by_module: dict[str, list[Item]] = {m: [] for m in module_order}
    for item in items:
        relfspath, *_ = item.location
        if relfspath not in items_by_module:
            item.warn(
                PytestCollectionWarning(
                    f"'{relfspath}' path not specified in module order."
                )
            )
            items_by_module[relfspath] = []
        items_by_module[relfspath].append(item)

    def get_sort_key(item: Item) -> int:
        _, lineno, _ = item.location
        if lineno is None:
            return 0
        return lineno

    for sublist in items_by_module.values():
        sublist.sort(key=get_sort_key)

    items_sorted: list[Item] = []
    for sublist in items_by_module.values():
        items_sorted += sublist

    if len(items) != len(items_sorted):
        raise IndexError(
            f"Not as many sorted items ({len(items_sorted)}) "
            f"as items initially ({len(items)})."
        )

    items[:] = items_sorted
