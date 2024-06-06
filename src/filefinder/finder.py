"""Main class."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck
import functools
import itertools
import logging
import os
import re
from collections.abc import Callable, Sequence
from copy import copy
from typing import Any, Protocol

from filefinder.group import Group, GroupKey
from filefinder.matches import Matches, get_groups_indices

logger = logging.getLogger(__name__)


class _FilterUserFunc(Protocol):
    """Defines the signature of filters callables (for static type checkers).

    See `<https://mypy.readthedocs.io/en/stable/protocols.html#callback-protocols>`__
    for details.
    """

    def __call__(
        self, __finder: "Finder", filename: str, matches: Matches, **kwargs: Any
    ) -> bool:
        ...


FilterPartial = Callable[["Finder", str, Matches], bool]


class Finder:
    """Find files using a filename pattern.

    The Finder object is the main entrance point to this library.
    Given a root directory and a filename pattern, it can search for all
    corresponding files.

    Parameters
    ----------
    root:
        The root directory of the filetree where all files can be found.
    pattern:
        A regular expression with the addition of 'groups'. See :ref:`find-files` for
        details.
    use_regex:
        If True, characters outside of groups are considered as valid regex (and
        not escaped). Default is False.
    scan_everything
        If true, look into all sub-directories up to a depth of :attr:`max_scan_depth` .
        This is appropriate if the pattern contains optional sub-directories. If false
        (default), check that every sub-directory matches its part of the regular
        expression, thus avoiding some work.
    """

    max_scan_depth: int = 32
    """Maximum sub-directory depth to scan when :attr:`scan_everything` is True."""

    def __init__(
        self,
        root: str,
        pattern: str,
        use_regex: bool = False,
        scan_everything: bool = False,
    ):
        self.root: str = root
        """The root directory of the finder."""
        self.use_regex: bool = use_regex
        """If True, characters outside of groups are considered as valid regex
        (and not escaped). Default is False."""

        self.scan_everything: bool = scan_everything
        """Whether to scan all subdirectories."""

        self._pattern: str

        self.groups: list[Group] = []
        self._segments: list[str] = []
        """Segments of the pattern. Used to replace specific groups.
        `['text before group 1', 'group 1',
        'text before group 2, 'group 2', ...]`
        """
        self._files: list[tuple[str, Matches]] = []
        self.scanned: bool = False
        """True if files have been scanned with current parameters.

        Is reset to False if the cache (of scanned files) is voided, for instance by
        operation like changing fixed values of groups.
        """

        self.filters: list[FilterPartial] = []
        """List of filters to apply to found files.

        Each value is a :func:`partial function<functools.partial>` with keyword
        arguments applied.
        """

        self.set_pattern(pattern)

    @property
    def n_groups(self) -> int:
        """Number of groups in pre-regex."""
        return len(self.groups)

    @property
    def files(self) -> list[tuple[str, Matches]]:
        """List of filenames and their matches.

        Will scan files when accessed and cache the result, if it has not
        already been done.
        """
        if not self.scanned:
            self.find_files()
        return self._files

    def __repr__(self) -> str:
        """Human readable information."""
        return "\n".join([super().__repr__(), self.__str__()])

    def __str__(self) -> str:
        """Human readable information."""
        s = [
            f"root: {self.root}",
            f"pattern: {self._pattern}",
            f"regex: {self.get_regex()}",
        ]

        fixed_groups = [
            (i, g.fixed_value)
            for i, g in enumerate(self.groups)
            if g.fixed_value is not None
        ]
        if fixed_groups:
            s.append("fixed groups:")
            s += [f"\t fixed #{i} to {v}" for i, v in fixed_groups]

        if not self.scanned:
            s.append("not scanned")
        else:
            s.append(f"scanned: found {len(self._files)} files")
        return "\n".join(s)

    def set_scan_everything(self, scan_everything: bool, /) -> None:
        """Set value for attribute :attr:`scan_everything`.

        Void cache if necessary.
        """
        if scan_everything != self.scan_everything:
            self.scan_everything = scan_everything
            self._void_cache()

    def set_use_regex(self, use_regex: bool, /) -> None:
        """Set value for attribute :attr:`use_regex`."""
        self.use_regex = use_regex

    def get_group_names(self, fixed: bool | None = None) -> set[str]:
        """Get the names of groups in the pattern.

        Parameters
        ----------
        fixed
            If True, only return names of groups with a fixed value. If False, return
            only those without a fixed value. If None (default), return for all groups.
        """
        groups = self.groups
        if fixed is not None:
            groups = [g for g in groups if g.fixed == fixed]

        return set(g.name for g in groups)

    def get_files(
        self,
        relative: bool = False,
        nested: Sequence[str | Sequence[str]] | None = None,
    ) -> list:
        """Return files that matches the regex.

        Lazily scan files: if files were already scanned, just return
        the stored list of files.
        Scanned files are flushed if the regex is changed (by fixing group
        for instance).

        Parameters
        ----------
        relative:
            If True, filenames are returned relative to the finder
            root directory. If not, paths are absolute (default).
        nested:
            If not None, return nested list of filenames with each level
            corresponding to a group, or set of group. Last set in the list
            is at the innermost level.

        Raises
        ------
        KeyError: A group name in `nested` is not found in the pattern.
        """

        def get_files(files_matches):
            if relative:
                return [f for f, _ in files_matches]
            return [self.get_absolute(f) for f, _ in files_matches]

        def get_key(matches: Matches, level: list[str]) -> str:
            return ":".join(
                [
                    match.get_match(parse=False)
                    for match in matches
                    if match.group.name in level
                ]
            )

        def nest(files_matches, levels, relative):
            if len(levels) == 0:
                return get_files(files_matches)

            level = levels[0]
            files_grouped = []
            matches: dict[str, int] = {}
            # We need to sort files by their value.
            # We use all unparsed matches joined in a single string as a key
            # (using get_key). We store it in a dictionnary, the value being
            # the corresponding index
            for f, m in files_matches:
                key = get_key(m, level)
                if key not in matches:
                    matches[key] = len(matches)
                    files_grouped.append([])
                files_grouped[matches[key]].append((f, m))

            return [nest(grp, levels[1:], relative) for grp in files_grouped]

        if not self.scanned:
            self.find_files()

        if nested is None:
            files = get_files(self._files)
        else:
            names = set(g.name for g in self.groups)
            nested = [[name] if isinstance(name, str) else name for name in nested]
            for name in itertools.chain(*nested):
                if name not in names:
                    raise KeyError(f"{name} is not in Finder groups.")
            files = nest(self._files, nested, relative)

        return files

    def get_relative(self, filename: str) -> str:
        """Get filename path relative to root."""
        return os.path.relpath(filename, self.root)

    def get_absolute(self, filename: str) -> str:
        """Get absolute path to filename."""
        return os.path.join(self.root, filename)

    def fix_group(self, key: GroupKey, value: str | Any, fix_discard: bool = False):
        """Fix a group to a string.

        Parameters
        ----------
        key:
            Can be the index of a group in the pattern (starts at 0), or the
            name of a group. If multiple groups share the same name, they are
            all fixed to the same value.
        value:
            Will replace the match for all files. Can be a string, or a value
            that will be formatted using the group format string.
            A list of values will be joined by the regex '|' OR.
            A string will be interpreted as a regular expression, so all special
            characters should be properly escaped.
        fix_discard:
            If True, groups with the 'discard' option will still be fixed.
            Default is False.
        """
        for m in self.get_groups(key):
            if not fix_discard and m.discard:
                continue
            m.fix_value(value)
        self._void_cache()

    def fix_groups(
        self,
        fixes: dict[Any, str | Any] | None = None,
        fix_discard: bool = False,
        **fixes_kw: str | Any,
    ):
        """Fix multiple groups at once.

        Parameters
        ----------
        fixes:
            Dictionnary of `{group key: value}`. See :func:`fix_group` for
            details.
        fix_discard:
            If True, groups with the 'discard' option will still be fixed.
            Default is False.
        fixes_kw:
            Same as `fixes`. Takes precedence.
        """
        if fixes is None:
            fixes = {}
        fixes.update(**fixes_kw)
        for f in fixes.items():
            self.fix_group(*f, fix_discard=fix_discard)

    def unfix_groups(self, *keys: str):
        """Unfix groups.

        Parameters
        ----------
        keys:
           Keys to find groups to unfix. See :func:`get_groups`.
           If no key is provided, all groups will be unfixed.
        """
        if not keys:
            for g in self.groups:
                g.unfix()
        else:
            for key in keys:
                groups = self.get_groups(key)
                for g in groups:
                    g.unfix()
        self._void_cache()

    def find_matches(self, filename: str, relative: bool = True) -> Matches | None:
        """Find matches for a given filename.

        Apply regex to `filename` and return the results as a :class:`~.matches.Matches`
        object. Fixed values are applied as normal.

        Parameters
        ----------
        filename:
            Filename to retrieve matches from.
        relative:
            True if the filename is relative to the finder root directory
            (default). If False, the filename is made relative before being
            matched.

        Returns
        -------
        matches
            A :class:`~.matches.Matches` object, or None if the filename did not match.
        """
        if not relative:
            filename = self.get_relative(filename)

        return Matches.from_filename(filename, self.get_regex(), self.groups)

    def make_filename(
        self,
        fixes: dict | None = None,
        relative: bool = False,
        **kw_fixes: Any,
    ) -> str:
        """Return a filename.

        Replace groups with provided values.
        All groups must be fixed prior, or with `fixes` argument.

        Parameters
        ----------
        fixes:
            Dictionnary of fixes (group name or index: value). For details, see
            :func:`fix_group`. Will (temporarily) supplant group fixed
            prior. If prior fix is a list, first item will be used.
        relative:
            If the filename should be relative to the finder root directory.
            Default is False.
        kw_fixes:
            Same as `fixes`. Takes precedence.

        Raises
        ------
        ValueError: `use_regex` is activated.
        """
        if self.use_regex:
            raise ValueError(
                "Cannot generate a valid filename if regex "
                "is present outside groups (`use_regex=True`)."
            )

        if fixes is None:
            fixes = {}
        fixes.update(**kw_fixes)

        segments = self._segments.copy()
        groups = [copy(g) for g in self.groups]  # shallow copy (no reparsing of def)

        for i, g in enumerate(groups):
            if g.name in fixes:
                g.fix_value(fixes[g.name])
            if i in fixes:
                g.fix_value(fixes[i])

            if g.fixed_string is not None:
                segments[2 * i + 1] = g.fixed_string
            else:
                raise ValueError(f"Group '{g!s}' has no fixed value.")

        filename = "".join(segments).replace("/", os.sep)

        if not relative:
            filename = self.get_absolute(filename)

        return filename

    def get_pattern(self) -> str:
        """Get filename pattern."""
        return self._pattern

    def set_pattern(self, pattern: str):
        """Set pattern and parse for group objects."""
        self._void_cache()
        self._pattern = pattern
        groups_starts = [m.start() + 1 for m in re.finditer(r"%\(", pattern)]

        # This finds the matching end parenthesis for each group start
        self.groups = []
        splits = [0]  # separation between groups
        for idx, start in enumerate(groups_starts):
            end = None
            level = 1
            for i, c in enumerate(pattern[start + 1 :]):
                if c == "(":
                    level += 1
                elif c == ")":
                    level -= 1
                    if level == 0:  # matching parenthesis
                        end = start + i + 1
                        break

            if end is None:  # did not find matching parenthesis :(
                end = start + 6
                substr = pattern[start - 1 : end]
                if end < len(self._pattern):
                    substr += "..."
                raise ValueError(f"No group end found for '{substr}'")

            self.groups.append(Group(pattern[start + 1 : end], idx))
            splits += [start - 1, end + 1]  # -1 removes the %

        self._segments = [pattern[i:j] for i, j in zip(splits, splits[1:] + [None])]

    def _get_regex(self) -> str:
        segments = self._segments.copy()
        if not self.use_regex:
            # escape regex outside groups
            segments = [
                s if (i % 2 == 1) else re.escape(s) for i, s in enumerate(segments)
            ]

        for idx, group in enumerate(self.groups):
            segments[2 * idx + 1] = group.get_regex()

        return "".join(segments)

    def get_regex(self) -> str:
        """Return regex."""
        return self._get_regex().replace("/", re.escape(os.sep))

    def get_regex_subdirs(self) -> list[str]:
        """Return regexes for each sub-directory."""
        return self._get_regex().split("/")

    def add_filter(self, func: _FilterUserFunc, **kwargs: Any):
        """Add a filter with which to select scanned files.

        See :doc:`/filtering` for details.

        :rtype func: Callable

        Parameters
        ----------
        func: ~collections.abc.Callable[[Finder, str, Matches, ...], bool]
            Callable that returns True if the file is to be kept, False otherwise.
        kwargs
            Will be passed to the function when executed.
        """
        filt = functools.partial(func, **kwargs)
        self.filters.append(filt)
        self._apply_filters(filt)

    def clear_filters(self) -> None:
        """Remove all filters."""
        self.filters.clear()
        self._void_cache()

    def _apply_filters(self, filter: FilterPartial | None = None) -> None:
        filters = [filter] if filter is not None else self.filters
        kept_files = []
        for filename, matches in self._files:
            if all(filt(self, filename, matches) for filt in filters):
                kept_files.append((filename, matches))
        self._files = kept_files

    def find_files(self) -> None:
        """Find files to scan and store them.

        Is automatically called when accessing :attr:`files` or :func:`get_files`. Apply
        all filters and sort files alphabetically.
        """
        if self.scan_everything:
            self._find_files_scan_everything()
        else:
            self._find_files_subdirectories()

        if self.filters:
            self._apply_filters()

        self._files.sort(key=lambda x: x[0])

    def _find_files_scan_everything(self) -> None:
        """Find files checking every sub-directory.

        Because having to check if a sub-directory matches the pattern is difficult,
        this allows for more exotic patterns where a folder separator can appear in a
        capturing group, by example for optional sub-directories.

        This will the whole filetree under :attr:`root_directory` and check every file
        found, which can be significant work in some cases.
        """
        pattern = re.compile(self.get_regex())
        files_matched = []

        for dirpath, dirnames, filenames in os.walk(self.root):
            depth = dirpath.rstrip(os.sep).count(os.sep) - self.root.rstrip(
                os.sep
            ).count(os.sep)
            if depth > self.max_scan_depth:
                dirnames.clear()

            for f in filenames:
                to_root = self.get_relative(os.path.join(dirpath, f))
                matches = Matches.from_filename(to_root, pattern, self.groups)
                if matches is not None:
                    files_matched.append((to_root, matches))

        self.scanned = True
        self._files = files_matched

    def _find_files_subdirectories(self) -> None:
        """Find files checking sub-directories along the way.

        Each sub-directory must match against its corresponding part of the generated
        regular expression. This is ill suited if any group contains a folder
        separator. But it will limit the number of sub-directories to explore and
        thus the number of files to check.
        """
        max_log_lines = 3

        subpatterns = [re.compile(rgx) for rgx in self.get_regex_subdirs()]
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            depth = dirpath.rstrip(os.sep).count(os.sep) - self.root.rstrip(
                os.sep
            ).count(os.sep)
            pattern = subpatterns[depth]

            if depth == len(subpatterns) - 1:
                dirnames.clear()  # look no deeper
                files += [
                    self.get_relative(os.path.join(dirpath, f)) for f in filenames
                ]
            elif logger.isEnabledFor(logging.DEBUG):
                dirlogs = dirnames[:max_log_lines]
                if len(dirnames) > max_log_lines:
                    dirlogs += ["..."]
                logger.debug(
                    "depth: %d, pattern: %s, folders:\n\t%s",
                    depth,
                    pattern.pattern,
                    "\n\t".join(dirlogs),
                )

            # Removes directories not matching regex
            to_remove = [d for d in dirnames if not pattern.fullmatch(d)]
            for d in to_remove:
                dirnames.remove(d)

        logger.debug("Found %s files in sub-directories", len(files))

        # Now only retain files that match the full pattern
        pattern = re.compile(self.get_regex())
        files_matched = []

        for f in files:
            matches = Matches.from_filename(f, pattern, self.groups)
            if matches is not None:
                files_matched.append((f, matches))

        if logger.isEnabledFor(logging.DEBUG):
            filelogs = files[:max_log_lines]
            if len(files) > max_log_lines:
                filelogs += ["..."]
            logger.debug(
                "regex: %s, files:\n\t%s", pattern.pattern, "\n\t".join(filelogs)
            )
            logger.debug("Found %s matching files in %s", len(files_matched), self.root)

        self.scanned = True
        self._files = files_matched

    def _void_cache(self) -> None:
        self.scanned = False
        self._files.clear()

    def get_groups(self, key: GroupKey) -> list[Group]:
        """Return list of groups corresponding to key.

        Parameters
        ----------
        key: int, str, or list of int
            Can be group index, name, or group+name combination with the
            syntax: 'group:name'.

        Returns
        -------
        List of groups corresponding to key.

        Raises
        ------
        KeyError: No group found.
        TypeError: Key type is not valid.
        """
        selected = get_groups_indices(self.groups, key)
        groups = [self.groups[i] for i in selected]
        return groups
