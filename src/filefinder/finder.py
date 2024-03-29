"""Main class."""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

from __future__ import annotations
import os
import logging
import re

from typing import Any, Callable, Dict, List, Tuple

from filefinder.matcher import (Matcher, Matches,
                                get_matchers_indices,
                                InvalidMatcher)

log = logging.getLogger(__name__)


class Finder():
    """Find files using a pre-regex.

    Parameters
    ----------
    root: str
        The root directory of a filetree where all files can be found.
    pregex: str
        The pre-regex. A regular expression with added 'Matchers'.
        Only the matchers vary from file to file. See documentation
        for details.
    use_regex: bool
        Characters outside of matchers are considered as valid regex (and not
        escaped) if True. Default is False.
    replacements: str, optional
        Matchers to replace by a string:
        `'matcher name' = 'replacement string'`.

    Attributes
    ----------
    root: str
        The root directory of the finder.
    use_regex: bool
        Characters outside of matchers are considered as valid regex (and not
        escaped) if true.
    """

    def __init__(self, root: str, pregex: str, use_regex: bool = False,
                 **replacements: str):

        if isinstance(root, (list, tuple)):
            root = os.path.join(*root)
        self.root: str = root
        self.use_regex: bool = use_regex

        self._pregex: str = ''
        self._regex: str = ''

        self._pattern: re.Pattern | None = None
        self._matchers: List[Matcher] = []
        self._segments: List[str] = []
        """Segments of the pre-regex. Used to replace specific matchers.
        `['text before matcher 1', 'matcher 1',
        'text before matcher 2, 'matcher 2', ...]`
        """
        self._fixed_matchers: Dict[str, str] = dict()
        self._files: List[Tuple[str, Matcher]] = []
        self._scanned: bool = False

        self.set_pregex(pregex, **replacements)
        self._update_regex()

    @property
    def n_matchers(self) -> int:
        """Number of matchers in pre-regex."""
        return len(self._matchers)

    @property
    def scanned(self) -> bool:
        """If files have been scanned."""
        return self._scanned

    @property
    def files(self) -> List[Tuple[str, Matches]]:
        """List of filenames and their matches.

        Will scan files if not already done.
        """
        if not self._scanned:
            self.find_files()
        return self._files

    def __repr__(self):
        return '\n'.join([super().__repr__(), self.__str__()])

    def __str__(self):
        s = ['root: {}'.format(self.root)]
        s += ["pre-regex: {}".format(self._pregex)]
        if self._regex is not None:
            s += ["regex: {}".format(self._regex)]
        else:
            s += ["regex not created"]
        if self._fixed_matchers:
            s += ["fixed matchers:"]
            s += ["\t fixed #{} to {}".format(i, v)
                  for i, v in self._fixed_matchers.items()]
        if not self._scanned:
            s += ["not scanned"]
        else:
            s += ["scanned: found {} files".format(len(self._files))]
        return '\n'.join(s)

    def get_files(self, relative: bool = False,
                  nested: List[str] | None = None) -> List[str]:
        """Return files that matches the regex.

        Lazily scan files: if files were already scanned, just return
        the stored list of files.
        Scanned files are flushed if the regex is changed (by fixing matcher
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
            matchers without a group.

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
                            if m_.matcher.group == group])

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
            groups = [m.group for m in self._matchers]
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

    def fix_matcher(
            self, key: int | str | Tuple[str],
            value: Any,
            fix_discard: bool = False
    ):
        """Fix a matcher to a string.

        Parameters
        ----------
        key: int, or str, or tuple of str of length 2.
            If int, is matcher index, starts at 0.
            If str, can be matcher name, or a group and name combination with
            the syntax 'group:name'.
            When using strings, if multiple matchers are found with the same
            name or group/name combination, all are fixed to the same value.
        value: str or value, or list of
            Will replace the match for all files. Can be a string, or a value
            that will be formatted using the matcher format string.
            A list of values will be joined by the regex '|' OR.
            Special characters should be properly escaped in strings.
        fix_discard: bool
            If True, matchers with the 'discard' option will still be fixed.
            Default is False.
        """
        self._fix_matcher_no_update(key, value, fix_discard)
        self._update_regex()

    def _fix_matcher_no_update(self, key, value, fix_discard):
        for m in self.get_matchers(key):
            if not fix_discard and m.discard:
                continue
            self._fixed_matchers[m.idx] = value

    def fix_matchers(
            self, fixes: Dict[int | str | Tuple[str], Any] = None,
            fix_discard: bool = False,
            **fixes_kw
    ):
        """Fix multiple values at once.

        Parameters
        ----------
        fixes: dict
            Dictionnary of matcher key: value. See :func:`fix_matcher` for
            details. If None, no matcher will be fixed.
        fix_discard: bool
            If True, matchers with the 'discard' option will still be fixed.
            Default is False.
        fixes_kw:
            Same as `fixes`. Takes precedence.
        """
        if fixes is None:
            fixes = {}
        fixes.update(fixes_kw)
        for f in fixes.items():
            self._fix_matcher_no_update(*f, fix_discard=fix_discard)
        self._update_regex()

    def unfix_matchers(self, *keys: str):
        """Unfix matchers.

        Parameters
        ----------
        keys: str
           Keys to find matchers to unfix. See :func:`get_matchers`.
           If no key is provided, all matchers will be unfixed.
        """
        if not keys:
            self._fixed_matchers = {}
        else:
            for key in keys:
                matchers = self.get_matchers(key)
                for m in matchers:
                    self._fixed_matchers.pop(m.idx, None)
        self._update_regex()

    def get_matches(self, filename: str,
                    relative: bool = True) -> Matches:
        """Get matches for a given filename.

        Apply regex to `filename` and return the results as a
        :class:`Matches<filefinder.matcher.Matches>` object.

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
            Not as many matches as matchers.
        """
        if not self._regex:
            raise AttributeError("Finder is missing a regex.")

        if not relative:
            filename = self.get_relative(filename)

        return Matches(self._matchers, filename, re.compile(self._regex))

    def get_filename(self, fixes: Dict | None = None, relative: bool = False,
                     **kw_fixes: Any) -> str:
        """Return a filename.

        Replace matchers with provided values.
        All matchers must be fixed prior, or with `fixes` argument.

        Parameters
        ----------
        fixes: dict
            Dictionnary of fixes (matcher key: value). For details, see
            :func:`fix_matcher`. Will (temporarily) supplant matcher fixed
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
            raise ValueError("Cannot generate a valid filename if regex "
                             "is present outside matchers.")

        fixed_matchers = self._fixed_matchers.copy()
        if fixes is None:
            fixes = {}
        fixes.update(kw_fixes)
        for key, value in fixes.items():
            for m in self.get_matchers(key):
                fixed_matchers[m.idx] = value

        non_fixed = [i for i in range(self.n_matchers)
                     if i not in fixed_matchers]
        if any(non_fixed):
            log.error("Matchers not fixed: %s",
                      ', '.join([str(self._matchers[i]) for i in non_fixed]))
            raise TypeError("Not all matchers were fixed.")

        segments = self._segments.copy()

        for idx, value in fixed_matchers.items():
            if isinstance(value, bool):
                value = self._matchers[idx].opt[value]
            if isinstance(value, (list, tuple)):
                value = value[0]
            if not isinstance(value, str):
                value = self._matchers[idx].format(value)
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

    def set_pregex(self, pregex: str, **replacements: str):
        """Set pre-regex.

        Apply replacements.
        """
        pregex = pregex.strip()
        for k, z in replacements.items():
            pregex = pregex.replace("%({:s})".format(k), z)
        self._pregex = pregex
        self._scan_pregex()
        self._update_regex()

    def _scan_pregex(self):
        """Scan pregex for matchers.

        Add matchers objects to self.
        Set segments attribute.
        """
        matchers_starts = [m.start()+1
                           for m in re.finditer(r'%\(', self._pregex)]

        self._matchers = []
        splits = [0]
        for idx, start in enumerate(matchers_starts):
            end = None
            level = 1
            for i, c in enumerate(self._pregex[start+1:]):
                if c == "(":
                    level += 1
                elif c == ")":
                    level -= 1
                    if level == 0:
                        end = start+i+1
                        break

            if end is None:
                end = start+6
                substr = self._pregex[start-1:end]
                if end < len(self._pregex):
                    substr += '...'
                raise ValueError("No matcher end found for '{}'"
                                 .format(substr))

            try:
                self._matchers.append(Matcher(self._pregex[start+1:end], idx))
                splits += [start-1, end+1]  # -1 removes the %
            except InvalidMatcher:
                pass

        self._segments = [self._pregex[i:j]
                          for i, j in zip(splits, splits[1:]+[None])]

        # Replace matcher by its regex
        for idx, m in enumerate(self._matchers):
            self._segments[2*idx+1] = m.get_regex()

    def _update_regex(self):
        """Update regex.

        Set fixed matchers. Compute regex. Scrap previous scanning.
        """
        segments = self._segments.copy()
        if not self.use_regex:
            for i, s in enumerate(segments):
                # Escape outside matchers
                segments[i] = s if i % 2 == 1 else re.escape(s)

        for idx, value in self._fixed_matchers.items():
            if isinstance(value, bool):
                if isinstance(self._matchers[idx].opt, tuple):
                    value = self._matchers[idx].opt[value]
            if not isinstance(value, (list, tuple)):
                value = [value]
            value = [v if isinstance(v, str)
                     else re.escape(self._matchers[idx].format(v))
                     for v in value]
            segments[2*idx+1] = '({})'.format('|'.join(value))

        self._regex = ''.join(segments)
        self._scanned = False
        self._files = []

    def find_files(self):
        """Find files to scan and store them.

        Is automatically called when accessing :attr:`files` or
        :func:`get_files`.
        Sort files alphabetically.

        Raises
        ------
        AttributeError
            If no regex is set.
        IndexError
            If no files are found in the filetree.
        """
        if self._regex is None:
            self.create_regex()
        if self._regex == '':
            raise AttributeError("Finder is missing a regex.")

        subpatterns = [re.compile(rgx)
                       for rgx in self._regex.split(os.path.sep)]
        files = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            # Feels hacky, better way ?
            depth = dirpath.count(os.sep) - self.root.count(os.sep)
            pattern = subpatterns[depth]

            if depth == len(subpatterns)-1:
                dirnames.clear()  # Look no deeper
                files += [self.get_relative(os.path.join(dirpath, f))
                          for f in filenames]
            else:
                dirlogs = dirnames[:3]
                if len(dirnames) > 3:
                    dirlogs += ['...']
                log.debug('depth: %d, pattern: %s, folders:\n\t%s',
                          depth, pattern.pattern, '\n\t'.join(dirlogs))

            # Removes directories not matching regex
            # We do double regex on directories, good enough
            to_remove = [d for d in dirnames if not pattern.fullmatch(d)]
            for d in to_remove:
                dirnames.remove(d)

        files.sort()

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
        log.debug("regex: %s, files:\n\t%s", self._regex, '\n\t'.join(filelogs))
        log.debug("Found %s matching files in %s",
                  len(files_matched), self.root)

        self._scanned = True
        self._files = files_matched

    def get_matchers(self, key: int | str) -> List[Matcher]:
        """Return list of matchers corresponding to key.

        Parameters
        ----------
        key: int, str, or list of int
            Can be matcher index, name, or group+name combination with the
            syntax: 'group:name'.

        Returns
        -------
        List of matchers corresponding to key.

        Raises
        ------
        KeyError
            No matcher found.
        TypeError
            Key type is not valid.
        """
        selected = get_matchers_indices(self._matchers, key)
        matchers = [self._matchers[i] for i in selected]
        return matchers
