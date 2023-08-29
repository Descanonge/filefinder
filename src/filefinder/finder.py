"""Main class."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import logging
import os
import re
from typing import Any, Callable

from filefinder.group import Group, get_groups_indices
from filefinder.matches import Matches

logger = logging.getLogger(__name__)


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
        A regular expression with added 'groups'. See :ref:`Pattern` for
        details.
    use_regex:
        If True, characters outside of groups are considered as valid regex (and
        not escaped). Default is False.
    """

    def __init__(self, root: str, pattern: str, use_regex: bool = False):

        if isinstance(root, (list, tuple)):
            root = os.path.join(*root)
        self.root: str = root
        """The root directory of the finder."""
        self.use_regex: bool = use_regex
        """If True, characters outside of groups are considered as valid regex
        (and not escaped). Default is False."""

        self._pattern: str = pattern

        self._groups: list[Group] = []
        self._segments: list[str] = []
        """Segments of the pattern. Used to replace specific groups.
        `['text before group 1', 'group 1',
        'text before group 2, 'group 2', ...]`
        """
        self._files: list[tuple[str, Group]] = []
        self._scanned: bool = False

        self._parse_pattern()

    @property
    def n_groups(self) -> int:
        """Number of groups in pre-regex."""
        return len(self._groups)

    @property
    def scanned(self) -> bool:
        """If files have been scanned."""
        return self._scanned

    @property
    def files(self) -> list[tuple[str, Matches]]:
        """List of filenames and their matches.

        Will scan files when accessed and cache the result, if it has not
        already been done.
        """
        if not self._scanned:
            self.find_files()
        return self._files

    def __repr__(self):
    @property
    def groups(self) -> Iterator[Group]:
        """Iterator on groups."""
        return iter(self._groups)

        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self):
        s = [
            f'root: {self.root}',
            f'pattern: {self._pattern}',
            f'regex: {self.get_regex()}'
        ]

        fixed_groups = [
            (i, g.fixed_value)
            for i, g in enumerate(self._groups)
            if g.fixed_value is not None
        ]
        if fixed_groups:
            s.append('fixed groups:')
            s += [f'\t fixed #{i} to {v}'
                  for i, v in fixed_groups]

        if not self._scanned:
            s.append('not scanned')
        else:
            s.append(f'scanned: found {len(self._files)} files')
        return '\n'.join(s)

    def get_files(self, relative: bool = False,
                  nested: list[str] | None = None) -> list[str]:
        """Return files that matches the regex.

        Lazily scan files: if files were already scanned, just return
        the stored list of files.
        Scanned files are flushed if the regex is changed (by fixing group
        for instance).

        Parameters
        ----------
        relative: bool
            If True, filenames are returned relative to the finder
            root directory. If not, paths are absolute (default).
        nested: list of str
            If not None, return nested list of filenames with each level
            corresponding to a group in this argument. Last group in the list
            is at the innermost level. A level specified as None refer to
            groups without a group.

        Raises
        ------
        KeyError
            A level in `nested` is not in the pre-regex groups.
        """
        def _get_files(files_matches):
            if relative:
                return [f for f, _ in files_matches]
            return [self.get_absolute(f) for f, _ in files_matches]

        def get_match(m, group):
            return ''.join([m_.get_match(parsed=False) for m_ in m
                            if m_.group.group == group])

        def nest(files_matches, groups, relative):
            if len(groups) == 0:
                return _get_files(files_matches)

            group = groups[0]
            files_grouped = []
            matches = {}
            for f, m in files_matches:
                match = get_match(m, group)
                if match not in matches:
                    matches[match] = len(matches)
                    files_grouped.append([])
                files_grouped[matches[match]].append((f, m))

            return [nest(grp, groups[1:], relative) for grp in files_grouped]

        if not self.scanned:
            self.find_files()

        if nested is None:
            files = _get_files(self._files)
        else:
            groups = [m.group for m in self._groups]
            for g in nested:
                if g not in groups:
                    raise KeyError(f'{g} is not in Finder groups.')
            files = nest(self._files, nested, relative)

        return files

    def get_relative(self, filename: str) -> str:
        """Get filename path relative to root."""
        return os.path.relpath(filename, self.root)

    def get_absolute(self, filename: str) -> str:
        """Get absolute path to filename."""
        return os.path.join(self.root, filename)

    def fix_group(
            self, key: int | str,
            value: Any,
            fix_discard: bool = False
    ):
        """Fix a group to a string.

        Parameters
        ----------
        key: int, or str, or tuple of str of length 2.
            If int, is group index, starts at 0.
            If str, can be group name, or a group and name combination with
            the syntax 'group:name'.
            When using strings, if multiple groups are found with the same
            name or group/name combination, all are fixed to the same value.
        value: str or value, or list of
            Will replace the match for all files. Can be a string, or a value
            that will be formatted using the group format string.
            A list of values will be joined by the regex '|' OR.
            Special characters should be properly escaped in strings.
        fix_discard: bool
            If True, groups with the 'discard' option will still be fixed.
            Default is False.
        """
        for m in self.get_groups(key):
            if not fix_discard and m.discard:
                continue
            m.fix_value(value)
        # invalid the cached files
        self._scanned = False

    def fix_groups(
            self, fixes: dict[int | str | tuple[str], Any] = None,
            fix_discard: bool = False,
            **fixes_kw
    ):
        """Fix multiple values at once.

        Parameters
        ----------
        fixes: dict
            Dictionnary of group key: value. See :func:`fix_group` for
            details. If None, no group will be fixed.
        fix_discard: bool
            If True, groups with the 'discard' option will still be fixed.
            Default is False.
        fixes_kw:
            Same as `fixes`. Takes precedence.
        """
        if fixes is None:
            fixes = {}
        fixes.update(fixes_kw)
        for f in fixes.items():
            self.fix_group(*f, fix_discard=fix_discard)

    def unfix_groups(self, *keys: str):
        """Unfix groups.

        Parameters
        ----------
        keys: str
           Keys to find groups to unfix. See :func:`get_groups`.
           If no key is provided, all groups will be unfixed.
        """
        if not keys:
            for g in self._groups:
                g.unfix()
        else:
            for key in keys:
                groups = self.get_groups(key)
                for g in groups:
                    g.unfix()
        # invalid cached files
        self._scanned = False

    def get_matches(self, filename: str,
                    relative: bool = True) -> Matches:
        """Get matches for a given filename.

        Apply regex to `filename` and return the results as a
        :class:`Matches<filefinder.group.Matches>` object.

        Parameters
        ----------
        filename: str
            Filename to retrieve matches from.
        relative: bool
            True if the filename is relative to the finder root directory
            (default). If False, the filename is made relative before being
            matched.

        Raises
        ------
        AttributeError
            The regex is empty.
        ValueError
            The filename did not match the pattern.
        IndexError
            Not as many matches as groups.
        """
        if not relative:
            filename = self.get_relative(filename)

        regex = self.get_regex()
        return Matches(self._groups, filename, re.compile(regex))

    def get_filename(self, fixes: dict | None = None, relative: bool = False,
                     **kw_fixes: Any) -> str:
        """Return a filename.

        Replace groups with provided values.
        All groups must be fixed prior, or with `fixes` argument.

        Parameters
        ----------
        fixes: dict
            Dictionnary of fixes (group key: value). For details, see
            :func:`fix_group`. Will (temporarily) supplant group fixed
            prior. If prior fix is a list, first item will be used.
        relative: bool
            If the filename should be relative to the finder root directory.
            Default is False.
        kw_fixes:
            Same as `fixes`. Takes precedence.

        Raises
        ------
        ValueError
            `use_regex` is activated.
        """
        if self.use_regex:
            raise ValueError('Cannot generate a valid filename if regex '
                             'is present outside groups.')

        fixed_groups = {
            i: group.fixed_value
            for i, group in enumerate(self._groups)
            if group.fixed_value is not None
        }
        if fixes is None:
            fixes = {}
        fixes.update(kw_fixes)
        for key, value in fixes.items():
            for m in self.get_groups(key):
                fixed_groups[m.idx] = value

        non_fixed = [i for i in range(self.n_groups)
                     if i not in fixed_groups]
        if any(non_fixed):
            logger.error('Groups not fixed: %s',
                      ', '.join([str(self._groups[i]) for i in non_fixed]))
            raise TypeError('Not all groups were fixed.')

        segments = self._segments.copy()

        for idx, value in fixed_groups.items():
            if isinstance(value, bool):
                value = self._groups[idx].opt[value]
            if isinstance(value, (list, tuple)):
                value = value[0]
            if not isinstance(value, str):
                value = self._groups[idx].format(value)
            segments[2*idx+1] = value

        filename = ''.join(segments)

        if not relative:
            filename = self.get_absolute(filename)

        return filename

    def get_func_process_filename(self, func: Callable, relative: bool = True,
                                  *args, **kwargs) -> Callable:
        r"""Get a function that can preprocess a dataset.

        Written to be used as the 'process' argument of
        `xarray.open_mfdataset`. Allows to use a function with additional
        arguments, that can retrieve information from the filename.

        Parameters
        ----------
        func: Callable
            Input arguments (`xarray.Dataset`, filename: `str`,
            `Finder`, \*args, \*\*kwargs)
            Should return a Dataset.
            Filename is retrieved from the dataset encoding attribute.
        relative: If True (default), `filename` is made relative to the finder
            root. This is necessary to match the filename against the finder
            regex.
        args: optional
            Passed to `func` when called.
        kwargs: optional
            Passed to `func` when called.

        Returns
        -------
        Callable
             Function with the signature of the 'process' argument of
             `xarray.open_mfdataset`.

        Examples
        --------
        This retrieve the date from the filename, and add a time dimensions
        to the dataset with the corresponding value.
        >>> from filefinder import library
        ... def process(ds, filename, finder, default_date=None):
        ...     matches = finder.get_matches(filename)
        ...     date = library.get_date(matches, default_date=default_date)
        ...     ds = ds.assign_coords(time=[date])
        ...     return ds
        ...
        ... ds = xr.open_mfdataset(finder.get_files(),
        ...                        preprocess=finder.get_func_process_filename(
        ...     process, default_date={'hour': 12}))
        """
        def f(ds):
            filename = ds.encoding['source']
            if relative:
                filename = self.get_relative(filename)
            return func(ds, filename, self, *args, **kwargs)
        return f

    def _parse_pattern(self):
        """Parse pattern for group objects."""
        groups_starts = [m.start()+1
                         for m in re.finditer(r'%\(', self._pattern)]

        # This finds the matching end parenthesis for each group start
        self._groups = []
        splits = [0] # separation between groups
        for idx, start in enumerate(groups_starts):
            end = None
            level = 1
            for i, c in enumerate(self._pattern[start+1:]):
                if c == '(':
                    level += 1
                elif c == ')':
                    level -= 1
                    if level == 0:  # matching parenthesis
                        end = start+i+1
                        break

            if end is None:  # did not find matching parenthesis :(
                end = start+6
                substr = self._pattern[start-1:end]
                if end < len(self._pattern):
                    substr += '...'
                raise ValueError(f"No group end found for '{substr}'")

            try:
                self._groups.append(Group(self._pattern[start+1:end], idx))
                splits += [start-1, end+1]  # -1 removes the %
            except ValueError: # unable to parse group
                pass

        self._segments = [self._pattern[i:j]
                          for i, j in zip(splits, splits[1:]+[None])]

    def get_regex(self) -> str:
        """Return regex."""
        segments = self._segments.copy()
        if not self.use_regex:
            # escape regex outside groups
            segments = [
                s if (i % 2 == 1) else re.escape(s)
                for i, s in enumerate(segments)
            ]

        for idx, group in enumerate(self._groups):
            segments[2*idx+1] = group.get_regex()

        return ''.join(segments)

    def find_files(self):
        """Find files to scan and store them.

        Is automatically called when accessing :attr:`files` or
        :func:`get_files`.
        Sort files alphabetically.

        Raises
        ------
        IndexError
            If no files are found in the filetree.
        """
        regex = self.get_regex()

        # patterns for each filetree depth
        subpatterns = [re.compile(rgx)
                       for rgx in regex.split(os.path.sep)]
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Feels hacky, better way ?
            depth = (dirpath.rstrip(os.sep).count(os.sep)
                     - self.root.rstrip(os.sep).count(os.sep))
            pattern = subpatterns[depth]

            if depth == len(subpatterns)-1:
                dirnames.clear()  # Look no deeper
                files += [self.get_relative(os.path.join(dirpath, f))
                          for f in filenames]
            else:
                dirlogs = dirnames[:3]
                if len(dirnames) > 3:
                    dirlogs += ['...']
                logger.debug('depth: %d, pattern: %s, folders:\n\t%s',
                             depth, pattern.pattern, '\n\t'.join(dirlogs))

            # Removes directories not matching regex
            to_remove = [d for d in dirnames if not pattern.fullmatch(d)]
            for d in to_remove:
                dirnames.remove(d)

        files.sort()
        logger.debug('Found %s non-matching files in directories', len(files))

        files_matched = []
        for f in files:
            try:
                matches = self.get_matches(f, relative=True)
            except ValueError:  # Filename did not match pattern
                pass
            else:
                files_matched.append((f, matches))

        filelogs = files[:3]
        if len(files) > 3:
            filelogs += ['...']
        logger.debug('regex: %s, files:\n\t%s', regex, '\n\t'.join(filelogs))
        logger.debug('Found %s matching files in %s',
                     len(files_matched), self.root)

        self._scanned = True
        self._files = files_matched

    def get_groups(self, key: int | str) -> list[Group]:
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
        KeyError
            No group found.
        TypeError
            Key type is not valid.
        """
        selected = get_groups_indices(self._groups, key)
        groups = [self._groups[i] for i in selected]
        return groups
