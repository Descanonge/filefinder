"""Easily create and populate temporary directories."""

import datetime as dt
import itertools
import os
from collections.abc import Sequence
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from filefinder.finder import Finder


def date_range(
    start: tuple[int, int, int], interval: int, size: int
) -> list[dt.datetime]:
    return [dt.datetime(*start) + i * dt.timedelta(days=interval) for i in range(size)]


class TmpDirectory:
    """Temporary directory that can easily create files."""

    def __init__(self, tmp_path: Path, **kwargs: Any) -> None:  # noqa: ARG002
        self.files: list[Path] = []
        self.parent_dir = tmp_path
        self._base_dir = TemporaryDirectory(dir=self.parent_dir)
        self.base_dir = Path(self._base_dir.name)

    def create_file(self, filename: str | Path, *, save: bool = True) -> Path:
        new_file = self.base_dir / filename
        parent = new_file.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        new_file.touch()
        if save:
            self.files.append(new_file.relative_to(self.base_dir))
        return new_file

    def create_dir(self, dirname: str | Path) -> Path:
        new_dir = self.base_dir / dirname
        new_dir.mkdir()
        return new_dir

    def get_absolute(self, path: str | Path) -> Path:
        return self.base_dir / path


class TmpDirectoryExample(TmpDirectory):
    """An example of directory with files.

    Files are structured as `<Y>/test_<Y><m><d>_<float parameter>[_<int parameter>].txt`
    """

    dates: list[dt.datetime]
    params: list[float]
    options: list[int | None]

    def __init__(
        self,
        tmp_path: Path,
        dates: Sequence[dt.datetime] | None = None,
        params: Sequence[float] | None = None,
        options: Sequence[int | None] | None = None,
        *,
        create: bool = True,
        **kwargs: Any,
    ) -> None:
        super().__init__(tmp_path, **kwargs)

        if dates is None:
            dates = date_range((2000, 1, 1), interval=15, size=50)
        if params is None:
            params = [-1.5, 0.0, 1.5]
        if options is None:
            options = [None, 0, 1, 2]
        self.dates = list(dates)
        self.params = list(params)
        self.options = list(options)

        if create:
            self.create_files()

    @staticmethod
    def make_filename(date: dt.datetime, param: float, option: int | None) -> Path:
        option_s = "" if option is None else f"_{option:02d}"
        filename = (
            f"{date.year}{os.sep}test"
            f"_{date.strftime('%Y-%m-%d')}"
            f"_{param:.1f}{option_s}.txt"
        )
        return Path(filename)

    def make_filenames(
        self,
        dates: Sequence[dt.datetime] | None = None,
        params: Sequence[float] | None = None,
        options: Sequence[int | None] | None = None,
    ) -> list[Path]:
        if dates is None:
            dates = self.dates
        if params is None:
            params = self.params
        if options is None:
            options = self.options
        files = [
            self.make_filename(*args)
            for args in itertools.product(dates, params, options)
        ]
        files.sort()
        return files

    def get_filefinder(self) -> Finder:
        finder = Finder(
            "%(Y)/test_%(Y)-%(m)-%(d)_%(param:fmt=.1f)%(option:fmt=02d:pre=_:opt).txt",
            root=self.base_dir,
        )
        return finder

    def create_files(self, *, save: bool = True) -> None:
        for f in self.make_filenames():
            self.create_file(f, save=save)
