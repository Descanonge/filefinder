"""Generate date elements table for documentation."""

import argparse
from pathlib import Path

from tabulate import tabulate  # type: ignore

from filefinder.dates import DateElement


def main(outfile: Path) -> None:  # noqa: D103
    table = [["Name", "Element", "Regex", "Format"]]

    keys = sorted(DateElement.registered(), key=lambda x: (x.upper(), x[0].isupper()))
    for key in keys:
        elt = DateElement.get(key)

        regex = elt.regex
        regex = regex.replace("(?:", "(")
        regex = regex.replace("\\", r"\\")
        table.append([key, elt.description, regex, elt.fmt])

    table_str = tabulate(table, headers="firstrow", tablefmt="rst")

    if not outfile.exists() or outfile.read_text() != table_str:
        outfile.write_text(table_str)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("outfile")
    args = parser.parse_args()

    main(Path(args.outfile))
