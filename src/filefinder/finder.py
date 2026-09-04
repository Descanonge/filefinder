"""Main class."""

import datetime as dt
import itertools
import logging
import os
import re
import warnings
from collections.abc import Callable, Sequence
from copy import copy
from typing import Any, overload

from .filters import FilterByDate, FilterByGroup, FilterList
from .group import Group, GroupKey, get_date_names, get_groups_indices
from .matches import DefaultDate, FileMatch, GroupMatch

logger = logging.getLogger(__name__)


def _log_list(
    logger: logging.Logger,
    elements: Sequence[str],
    *,
    level: int = logging.DEBUG,
    max_log_lines: int = 4,
) -> None:
    """Log a list of elements. Truncate if too long."""
    if logger.isEnabledFor(level):
        is_long = len(elements) > max_log_lines
        i_max = max_log_lines - 2 if is_long else len(elements)
        for element in elements[:i_max]:
            logger.log(level, "\t%s", element)
        if is_long:
            logger.log(level, "\t...")
            logger.log(level, "\t%s", elements[-1])


def _handle_walk_error(exc: OSError) -> None:
    """Handle OS errors when scanning directories."""
    warnings.warn(str(exc), stacklevel=1)


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
        The filename pattern. See :doc:`/pattern` for details.
    use_regex:
        If True, characters outside of groups are considered as valid regex (and
        not escaped). Default is False.
    scan_everything:
        If true, look into all sub-directories up to a depth of :attr:`max_scan_depth` .
        This is appropriate if the pattern contains optional sub-directories. If false
        (default), check that every sub-directory matches its part of the regular
        expression, thus avoiding some work.
    follow_symlinks:
        If true, follow symbolic links pointing to directories when scanning for files.
        This may lead to infinite recursion.
    group_delimiters:
        Tuple of (prefix, start characters, end characters) that defines how groups are
        delimited in the pattern. Start and end character must be balanced within the
        group. Prefix can be empty. If None, the default `%()` is used.
    """

    max_scan_depth: int = 32
    """Maximum sub-directory depth to scan when :attr:`scan_everything` is True."""

    _group_delimiters: tuple[str, str, str] = ("%", "(", ")")
    """Delimiter characters of groups in the pattern."""

    def __init__(
        self,
        root: str,
        pattern: str,
        *,
        use_regex: bool = False,
        scan_everything: bool = False,
        follow_symlinks: bool = False,
        group_delimiters: tuple[str, str, str] | None = None,
    ) -> None:
        self.root: str = root
        """The root directory of the finder."""
        self.use_regex: bool = use_regex
        """If True, characters outside of groups are considered as valid regex
        (and not escaped). Default is False."""
        self.scan_everything: bool = scan_everything
        """Whether to scan all subdirectories."""
        self.follow_symlinks: bool = follow_symlinks
        """Whether to follow symbolic links to directories when scanning files."""

        if group_delimiters is not None:
            self._group_delimiters = group_delimiters

        self._pattern: str

        self.groups: list[Group] = []
        self._segments: list[str] = []
        """Segments of the pattern. Used to replace specific groups.
        `['text before group 1', 'group 1',
        'text before group 2, 'group 2', ..., 'last group', 'text after last group']`
        """
        self._matches: list[FileMatch] = []
        self.scanned: bool = False
        """True if files have been scanned with current parameters.

        Is reset to False if the cache (of scanned files) is cleared, for instance by
        operations like changing fixed values of groups.
        """

        self.filters: FilterList = FilterList()
        """List of filters to apply to found files."""

        self.set_pattern(pattern)

    @property
    def n_groups(self) -> int:
        """Number of groups in pre-regex."""
        return len(self.groups)

    @property
    def matches(self) -> list[FileMatch]:
        """List of matches objects.

        Lazily scan files: if files were already scanned, just return
        the stored list of matches.
        """
        if not self.scanned:
            self.find_files()
        return self._matches

    def __repr__(self) -> str:
        """Human readable information (long)."""
        s = [
            self.__class__.__qualname__,
            f"root: {self.root}",
            f"pattern: {self._pattern}",
            f"regex: {self.get_regex()}",
        ]

        fixed_groups = [
            (i, g.fixed_value) for i, g in enumerate(self.groups) if g.fixed
        ]
        if fixed_groups:
            s.append("fixed groups:")
            s += [f"\t fixed #{i} to {v}" for i, v in fixed_groups]

        if not self.scanned:
            s.append("not scanned")
        else:
            s.append(f"scanned: found {len(self._matches)} files")
        return "\n".join(s)

    def __str__(self) -> str:
        """Human readable information (short)."""
        return (
            f"{self.__class__.__qualname__}: "
            f"{self.root.rstrip('/')}/ {self.get_regex()}"
        )

    def set_scan_everything(self, scan_everything: bool) -> None:  # noqa: FBT001
        """Set value for attribute :attr:`scan_everything`."""
        if scan_everything != self.scan_everything:
            self.scan_everything = scan_everything
            self.clear_cache()

    def set_use_regex(self, use_regex: bool) -> None:  # noqa: FBT001
        """Set value for attribute :attr:`use_regex`."""
        if use_regex != self.use_regex:
            self.use_regex = use_regex
            self.clear_cache()

    def set_follow_symlinks(self, follow_symlinks: bool) -> None:  # noqa: FBT001
        """Set value for attribute :attr:`follow_symlinks`."""
        if follow_symlinks != self.follow_symlinks:
            self.follow_symlinks = follow_symlinks
            self.clear_cache()

    def get_group_names(self, *, fixed: bool | None = None) -> set[str]:
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

        return {g.name for g in groups}

    def get_date_names(self) -> set[str]:
        """Get the names of date pseudo-groups.

        Examples
        --------
        ::

            "%(start:Y)%(start:j)_%(end:Y)%(end:j)" -> {"start", "end"}
            "%(Y)-%(m)-%(d)" -> {"date"}
        """
        return get_date_names(self.groups)

    @overload
    def get_files(self, *, relative: bool = ...) -> list[str]: ...

    @overload
    def get_files(
        self, *, relative: bool = ..., nested: Sequence[str | Sequence[str]] = ...
    ) -> list: ...

    def get_files(
        self,
        *,
        relative: bool = False,
        nested: Sequence[str | Sequence[str]] | None = None,
    ) -> list[str]:
        """Return files that match the regex.

        Lazily scan files: if files were already scanned, just return
        the stored list of files.

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
        KeyError
            A group name in `nested` is not found in the pattern.
        """

        def get_files(matches: Sequence[FileMatch]) -> list[str]:
            return [m.get_filename(relative=relative) for m in matches]

        def get_key(filematch: FileMatch, level: Sequence[str]) -> str:
            i_groups = []
            for name in level:
                i_groups += get_groups_indices(filematch.groups, name)
            i_groups = list(set(i_groups))
            i_groups.sort()
            return ":".join(
                [filematch.matches[i].get_match(parse=False) for i in i_groups]
            )

        def nest(
            matches: Sequence[FileMatch],
            levels: Sequence[Sequence[str]],
            *,
            relative: bool,
        ) -> list:
            if len(levels) == 0:
                return get_files(matches)

            level = levels[0]
            files_grouped: list[list[FileMatch]] = []
            matches_by_value: dict[str, int] = {}
            # We need to sort files by their value.
            # We use all unparsed matches joined in a single string as a key
            # (using get_key). We store it in a dictionnary, the value being
            # the corresponding index
            for m in matches:
                key = get_key(m, level)
                if key not in matches_by_value:
                    matches_by_value[key] = len(matches_by_value)
                    files_grouped.append([])
                files_grouped[matches_by_value[key]].append(m)

            return [nest(grp, levels[1:], relative=relative) for grp in files_grouped]

        if not self.scanned:
            self.find_files()

        if nested is None:
            return get_files(self._matches)

        names = {g.name for g in self.groups}
        nested = [[name] if isinstance(name, str) else name for name in nested]
        for name in itertools.chain(*nested):
            if name not in names:
                raise KeyError(f"{name} is not in Finder groups.")
        return nest(self._matches, nested, relative=relative)

    def get_relative(self, filename: str) -> str:
        """Get filename path relative to root."""
        return os.path.relpath(filename, self.root)

    def get_absolute(self, filename: str) -> str:
        """Concatenate the finder root directory and a filename."""
        return os.path.join(self.root, filename)

    def fix(
        self,
        fixes: dict[Any, str | Any] | None = None,
        **fixes_kw: str | Any,
    ) -> None:
        """Fix groups to a value.

        Groups are selected with either their index in the pattern (starts at 0), or
        their name. If multiple groups share the same name, they are all fixed to the
        same value.

        Values can be a string, or a value that will be formatted using the group format
        string. A string will be interpreted as a regular expression, so all special
        characters should be properly escaped. A list of values will be joined by the
        regex '|' OR.

        Parameters
        ----------
        fixes:
            Dictionnary of `{group key: value}`.
        fixes_kw:
            Same as `fixes`. Takes precedence.
        """
        if fixes is None:
            fixes = {}
        fixes.update(**fixes_kw)
        self.clear_cache()
        date_names = self.get_date_names()
        for key, value in fixes.items():
            if key in date_names and not (
                isinstance(value, dt.date)
                or (
                    isinstance(value, Sequence)
                    and all(isinstance(v, dt.date) for v in value)
                )
            ):
                raise TypeError(
                    f"Date pseudo-group '{key}' can only be fixed with a datetime "
                    f"object or list thereof (received {type(value)})."
                )
            for group in self.get_groups(key):
                group.fix(value)

    def unfix(self, *keys: GroupKey) -> None:
        """Unfix groups.

        Parameters
        ----------
        keys:
           Keys to find groups to unfix. If no key is provided, all groups will be
           unfixed.
        """
        if not keys:
            keys = tuple(range(self.n_groups))

        for key in keys:
            groups = self.get_groups(key)
            for g in groups:
                g.unfix()

        self.clear_cache()

    def add_filter(self, func: Callable[..., bool], **kwargs: Any) -> None:
        """Add a filter with which to select scanned files.

        The filter will be applied to files already in the cache.

        Parameters
        ----------
        func
            Callable that takes in: the Finder instance, a `class:FileMatch` object, and
            optional kwargs. Returns True if the file is to be kept, False otherwise.
        kwargs
            Will be passed to the function when executed.
        """
        filt = self.filters.add(func, **kwargs)

        if self.scanned:
            self._matches = [m for m in self._matches if filt.is_valid(self, m)]

    def add_group_filter(
        self,
        key: GroupKey,
        func: Callable[..., bool],
        *,
        default_date: DefaultDate = None,
        pass_unparsed: bool = False,
        **kwargs: Any,
    ) -> None:
        """Fix a group value by using a filter function.

        When a file is scanned, if it matches the pattern, it will only be kept if
        `func` returns True when called with the group parsed value. If the group cannot
        parse the value: if `pass_unparse` is True the unparsed string will be passed to
        the predicate function nonetheless, otherwise it will not keep the file
        (default).

        Parameters
        ----------
        key:
            Can be the index of a group in the pattern (starts at 0), or the name of a
            group. If multiple groups share the same name, they are all fixed. If it is
            the name of a date pseudo-group, the function will receive a datetime
            object.
        func
            A function that takes the parsed value of the group and returns True if the
            corresponding file should be kept, or False otherwise. If multiple groups
            correspond to the key, **all** values will be tested successively.
        pass_unparsed
            In case the group cannot parse the string, if True pass the unparsed string
            to the predicate function `func` anyway. If False (default) the file will
            not be kept.
        default_date
            Default date elements to use when retrieving date.
        kwargs
            Will be passed to the function.
        """
        filt: FilterByGroup | FilterByDate
        if key in self.get_date_names():
            filt = self.filters.add_by_date(
                func, key, default_date=default_date, **kwargs
            )

        else:
            indices = get_groups_indices(self.groups, key)
            filt = self.filters.add_by_group(
                func, indices, pass_unparsed=pass_unparsed, **kwargs
            )

        if self.scanned:
            self._matches = [m for m in self._matches if filt.is_valid(self, m)]

    def remove_group_filters(self, *keys: str) -> None:
        """Remove group filters.

        Parameters
        ----------
        keys:
            Name of date pseudo-groups to remove filters from. If empty, all group
            filters will be removed.
        """
        date_names = self.get_date_names()
        if not keys:
            keys = tuple(date_names)

        for key in keys:
            if key in date_names:
                self.filters.remove_by_date(key)
            else:
                self.filters.remove_by_group(get_groups_indices(self.groups, key))

        self.clear_cache()

    def clear_filters(self) -> None:
        """Remove all filters."""
        self.filters.clear()
        self.clear_cache()

    def find_matches(
        self,
        filename: str,
        *,
        relative: bool = True,
        pattern: str | re.Pattern | None = None,
    ) -> FileMatch | None:
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
        pattern:
            Regex pattern to match the filename against (compiled or not). If left to
            None, it is automatically generated.

        Returns
        -------
        matches
            A :class:`~.matches.Matches` object, or None if the filename did not match.
        """
        if not relative:
            filename = self.get_relative(filename)

        if pattern is None:
            pattern = self.get_regex()

        if isinstance(pattern, str):
            pattern = re.compile(pattern)
        m = pattern.fullmatch(filename)

        if m is None:
            return None

        if len(self.groups) != len(m.groups()):
            raise IndexError(
                "Not as many captured matches as pattern groups. "
                "Does one of the group regex contains a capturing group?"
            )

        match_list = [
            GroupMatch.from_match(grp, m, i) for i, grp in enumerate(self.groups)
        ]
        return FileMatch(self.root, filename, match_list, self.groups)

    def make_filename(
        self,
        fixes: dict | None = None,
        *,
        relative: bool = False,
        **kw_fixes: Any,
    ) -> str:
        """Return a filename.

        Replace groups with provided values.
        All groups must be fixed prior, or with `fixes` argument.

        Only works if :attr:`use_regex` is set to False (default).

        Parameters
        ----------
        fixes:
            Dictionnary of fixes (group name or index: value). For details, see
            :func:`fix`. Will (temporarily) supplant group fixed prior. If prior fix is
            a list, first item will be used.
        relative:
            If the filename should be relative to the finder root directory.
            Default is False.
        kw_fixes:
            Same as `fixes`. Takes precedence.

        Raises
        ------
        KeyError
            Some group has no fixed value.
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
                g.fix(fixes[g.name])
            if i in fixes:
                g.fix(fixes[i])
            if g.date_name is not None and g.date_name in fixes:
                g.fix(fixes[g.date_name])

            if g.fixed_string is not None:
                segments[2 * i + 1] = (
                    g.fixed_string
                    if isinstance(g.fixed_string, str)
                    else g.fixed_string[0]
                )
            elif g.optional:
                segments[2 * i + 1] = ""
            else:
                raise KeyError(f"Group '{g!s}' has no fixed value.")

        filename = "".join(segments).replace("/", os.sep)

        if not relative:
            filename = self.get_absolute(filename)

        return filename

    def get_pattern(self) -> str:
        """Get filename pattern."""
        return self._pattern

    def set_pattern(self, pattern: str) -> None:
        """Set pattern and parse for group objects."""
        self.clear_cache()
        self._pattern = pattern

        found_groups = self._find_groups(pattern)

        self.groups = []
        splits = [0]  # separation between groups
        for idx, (specs, start, end) in enumerate(found_groups):
            self.groups.append(Group(specs, idx))
            splits += [start, end]

        self._segments = [
            pattern[i:j] for i, j in zip(splits, [*splits[1:], None], strict=False)
        ]

    def _find_groups(self, pattern: str) -> list[tuple[str, int, int]]:
        """Find the groups within the pattern and their corresponding string indices.

        Return for each group, in order of appearance in the pattern, a tuple of the
        string specification of the group, without delimiters and indices of the first
        and last characters of the group (including delimiters).

        This implementation finds the matching pair defined by the attribute
        :attr:`_group_delimiters`. A match of the start of a group that does not have a
        matching end will raise.
        """
        grp_prefix, grp_start, grp_end = self._group_delimiters
        pattern_starts = re.escape(f"{grp_prefix}{grp_start}")
        find_next = re.compile(f"({re.escape(grp_start)}|{re.escape(grp_end)})")

        groups_starts = [m.start() for m in re.finditer(pattern_starts, pattern)]

        output = []
        # This finds the matching end characters for each group start
        for start in groups_starts:
            end = None
            level = 1
            start_spec = start + len(grp_prefix) + len(grp_start)
            for m in find_next.finditer(pattern, pos=start_spec):
                if m.group() == grp_start:
                    level += 1
                elif m.group() == grp_end:
                    level -= 1
                    if level == 0:  # matching parenthesis
                        end = m.end()
                        end_spec = end - len(grp_end)
                        assert end_spec > 0
                        break

            if end is None:  # did not find matching parenthesis :(
                end = start + 6
                substr = pattern[start:end]
                if end < len(self._pattern):
                    substr += "..."
                raise ValueError(f"No group end found for '{substr}'")

            output.append((pattern[start_spec:end_spec], start, end))

        return output

    def get_regex(self, *, replace_dir_sep: bool = True) -> str:
        """Return regex.

        Parameters
        ----------
        replace_dir_sep:
            If True (default), replace "/" in the regex by the correct directory
            separator for the current OS.
        """
        segments = self._segments.copy()
        if not self.use_regex:
            # escape regex outside groups
            segments = [
                s if (i % 2 == 1) else re.escape(s) for i, s in enumerate(segments)
            ]

        for idx, group in enumerate(self.groups):
            segments[2 * idx + 1] = group.get_regex()

        regex = "".join(segments)

        if replace_dir_sep:
            regex = regex.replace("/", re.escape(os.sep))

        return regex

    def get_regex_subdirs(self) -> list[str]:
        """Return regexes for each sub-directory."""
        return self.get_regex(replace_dir_sep=False).split("/")

    def find_files(self) -> None:
        """Find files to scan and store them in cache.

        Is automatically called when accessing :attr:`matches` or :func:`get_files`.
        Apply all filters and sort files alphabetically.
        """
        if self.scanned:
            self.clear_cache()

        if self.scan_everything:
            self._find_files_scan_everything()
        else:
            self._find_files_subdirectories()

        self._matches.sort(key=lambda x: x.get_filename())

        logger.debug("Found %d files matching and filtered", len(self._matches))
        if len(self._matches) == 0:
            logger.info("Found no matching files (after filtering)")

        self.scanned = True

    def _add_file(self, filename: str, pattern: re.Pattern) -> None:
        """Add file to cache if it matches pattern and pass filters."""
        matches = self.find_matches(filename, relative=True, pattern=pattern)
        if matches is not None and self.filters.is_valid(self, matches):
            self._matches.append(matches)

    def _find_files_scan_everything(self) -> None:
        """Find files in all sub-directories.

        Because having to check if a sub-directory matches the pattern is difficult,
        this allows for more exotic patterns where a folder separator can appear in a
        capturing group, by example for optional sub-directories.

        This will scan the whole filetree under :attr:`root` and check every file found,
        which can be significant work in some cases.
        """
        pattern = re.compile(self.get_regex())

        for dirpath, dirnames, filenames in os.walk(
            self.root, followlinks=self.follow_symlinks, onerror=_handle_walk_error
        ):
            depth = dirpath.rstrip(os.sep).count(os.sep) - self.root.rstrip(
                os.sep
            ).count(os.sep)
            logger.debug(
                "Scanning in %s (depth %d/%d)", dirpath, depth, self.max_scan_depth
            )
            if depth > self.max_scan_depth:
                dirnames.clear()

            logger.debug("Found %d files", len(filenames))
            _log_list(logger, filenames, level=logging.DEBUG)
            for f in filenames:
                to_root = self.get_relative(os.path.join(dirpath, f))
                self._add_file(to_root, pattern)

    def _find_files_subdirectories(self) -> None:
        """Find files checking sub-directories along the way.

        Each sub-directory must match against its corresponding part of the generated
        regular expression. This is ill suited if any group contains a folder
        separator. But it will limit the number of sub-directories to explore and
        thus the number of files to check.
        """
        full_pattern = re.compile(self.get_regex())
        subpatterns = [re.compile(rgx) for rgx in self.get_regex_subdirs()]
        maxdepth = len(subpatterns) - 1
        for dirpath, dirnames, filenames in os.walk(
            self.root, followlinks=self.follow_symlinks, onerror=_handle_walk_error
        ):
            depth = dirpath.rstrip(os.sep).count(os.sep) - self.root.rstrip(
                os.sep
            ).count(os.sep)
            pattern = subpatterns[depth]

            logger.debug("Looking in %s (depth %d/%d)", dirpath, depth, maxdepth)
            if depth < maxdepth:
                logger.debug(
                    "Found %d directories to match against %s",
                    len(dirnames),
                    pattern.pattern,
                )
                _log_list(logger, dirnames, level=logging.DEBUG)

                # Removes directories not matching regex
                to_remove = [d for d in dirnames if not pattern.fullmatch(d)]
                for d in to_remove:
                    dirnames.remove(d)

            else:
                dirnames.clear()  # look no deeper

                logger.debug("Found %d files", len(filenames))
                _log_list(logger, filenames, level=logging.DEBUG)

                for f in filenames:
                    to_root = self.get_relative(os.path.join(dirpath, f))
                    # logger.debug("Matching %s to %s", to_root, full_pattern.pattern)
                    self._add_file(to_root, full_pattern)

    def clear_cache(self) -> None:
        """Clear the cache."""
        self.scanned = False
        self._matches.clear()

    def get_groups(self, key: GroupKey) -> list[Group]:
        """Return list of groups corresponding to key.

        Parameters
        ----------
        key: int, str, or list of int
            Can be group index or name.

        Returns
        -------
        List of groups corresponding to key.

        Raises
        ------
        KeyError
            No group found.
        TypeError
            Key type is not valid.
        """
        selected = get_groups_indices(self.groups, key)
        return [self.groups[i] for i in selected]
