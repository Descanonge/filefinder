"""Generation of parameters."""

import itertools
import math
import os
import re
import sys
import typing as t
from collections import abc
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from hypothesis import strategies as st

from filefinder.format import Format, FormatError
from filefinder.group import Group
from filefinder.util import datetime_keys

MAX_CODEPOINT = 1024
MAX_TEXT_SIZE = 32

if sys.platform in ["win32", "cygwin"]:
    FORBIDDEN_CHAR = set('<>:;"\\|?.*')
elif sys.platform == "darwin":
    FORBIDDEN_CHAR = set(":;")
else:
    FORBIDDEN_CHAR = set()


T = t.TypeVar("T")


class Drawer(t.Protocol):
    def __call__(self, __strat: st.SearchStrategy[T]) -> T: ...


class FilesDefinition:
    parent_dir: Path
    _base_dir: TemporaryDirectory
    base_dir: Path

    def __init__(self, tmp_path: Path, **kwargs):
        self.parent_dir = tmp_path
        self._base_dir = TemporaryDirectory(dir=self.parent_dir)
        self.base_dir = Path(self._base_dir.name)

    def create_file(self, filename: str | Path) -> str:
        new_file = self.base_dir / filename
        parent = new_file.parent
        if not parent.exists():
            parent.mkdir(parents=True, exist_ok=True)
        new_file.touch()
        return str(new_file)

    def create_dir(self, dirname: str | Path) -> str:
        new_dir = self.base_dir / dirname
        new_dir.mkdir()
        return str(new_dir)

    def get_absolute(self, path: str) -> str:
        return str(self.base_dir / path)


class TmpDirTest:
    def get_files_def(self, tmp_path: Path, **kwargs) -> FilesDefinition:
        return FilesDefinition(tmp_path, **kwargs)


class FilesDefinitionAuto(FilesDefinition):
    dates: list[datetime]
    params: list[float]
    options: list[bool]

    datadir: str

    files: list[str]

    def __init__(
        self,
        tmp_path: Path,
        dates: abc.Sequence[datetime] | None = None,
        params: abc.Sequence[float] | None = None,
        options: abc.Sequence[bool] | None = None,
        datadir: str | None = None,
        create: bool = False,
        **kwargs,
    ):
        super().__init__(tmp_path, **kwargs)

        if dates is None:
            dates = [datetime(2000, 1, 1) + i * timedelta(days=15) for i in range(50)]
        if params is None:
            params = [-1.5, 0.0, 1.5]
        if options is None:
            options = [False, True]
        if datadir is None:
            datadir = "data"
        self.dates = list(dates)
        self.params = list(params)
        self.options = list(options)
        self.datadir = datadir

        self.files = self.make_filenames()

        if create:
            self.create_files()

    @staticmethod
    def make_filename(date: datetime, param: float, option: bool) -> str:
        filename = (
            f"{date.year}{os.sep}test"
            f"_{date.strftime('%Y-%m-%d')}"
            f"_{param:.1f}{'_yes' if option else ''}.ext"
        )
        return filename

    def make_filenames(
        self,
        dates: abc.Sequence[datetime] | None = None,
        params: abc.Sequence[float] | None = None,
        options: abc.Sequence[bool] | None = None,
    ) -> list[str]:
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

    def create_files(self):
        self.create_dir(self.datadir)

        for f in self.files:
            self.create_file(os.path.join(self.datadir, f))


def form(fmt: str, value: t.Any) -> str:
    """Format a value from a format string.

    The format does not include the starting ':'.
    """
    return f"{{:{fmt}}}".format(value)


def build_exclude(
    exclude: set[str] | None = None,
    for_pattern: bool = False,
    for_filename: bool = False,
) -> set[str]:
    """Build a set of characters to exclude.

    Parameters
    ----------
    exclude
        Base set of characters to exclude. Default (None) is empty.
    for_pattern
        If True, exclude group-related characters `%()`.
    for_filename
        If True, exclude characters forbidden in filenames on current platform. Also
        exclude the filefinder default folder separator '/', whatever the platform.
    """
    if exclude is None:
        exclude = set()
    if for_pattern:
        exclude |= set("%()")
    if for_filename:
        exclude |= FORBIDDEN_CHAR
        exclude.add("/")
    return exclude


@dataclass
class FormatSpecs:
    """Store format specs and generate format string."""

    align: str = ""
    """Alignement. Empty or [ <>=^]."""
    fill: str = ""
    """Fill character. Empty or any character."""
    sign: str = ""
    """Sign indication. Empty or [ +-]."""
    alt: str = ""
    """Alternate form. Empty or '#.'"""
    zero: str = ""
    """Zero fill. Empty or '0'."""
    grouping: str = ""
    """Thousands grouping character. Empty or [_,]"""
    width: int | None = None
    """String length (not enforced).

    None is for no width specified.
    """
    precision: int | None = None
    """Number of digits after decimal.

    None is for no precision specified.
    """
    kind: str = "s"
    """Type of format [sdfeE]."""

    def __str__(self) -> str:
        return self.format_string

    @property
    def width_str(self) -> str:
        """Width part of the format string."""
        return "" if self.width is None else f"{self.width:d}"

    @property
    def precision_str(self) -> str:
        """Precision part of the format string."""
        return "" if self.precision is None else f".{self.precision:d}"

    @property
    def format_string(self) -> str:
        """Generate a format string from instance parameters."""
        fmt = ""
        if self.align:
            fmt += self.fill + self.align

        if self.kind == "s":
            fmt += self.zero + self.width_str + "s"
            return fmt

        fmt += self.sign + self.alt + self.zero + self.width_str + self.grouping

        if self.kind in "feE":
            fmt += self.precision_str

        return fmt + self.kind

    def is_valid(self) -> bool:
        """Return if format string is valid according to Format object."""
        try:
            Format(self.format_string)
        except FormatError:
            return False
        return True

    def get_value_strategy(
        self, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy[str | int | float]:
        """Return appropriate strategy for this format instance.

        Take into account precision.
        """
        strat: st.SearchStrategy

        # Integers
        if self.kind == "d":
            return st.integers()

        # String
        if self.kind == "s":
            exclude = build_exclude(for_pattern=for_pattern, for_filename=for_filename)
            exclude_cat = ["C"]
            if sys.platform in ["win32", "cygwin", "darwin"]:
                exclude_cat += ["Z", "P", "S", "M"]
            strat = st.text(
                alphabet=st.characters(
                    max_codepoint=MAX_CODEPOINT,
                    exclude_categories=exclude_cat,  # type: ignore[arg-type]
                    exclude_characters=exclude,
                ),
                max_size=MAX_TEXT_SIZE,
            )
            # do not allow fill character (if it exists) on the edges of the string
            # this gives ambiguous parsing
            fill = self.fill if self.fill and self.align else " "
            strat = strat.map(lambda s: form(self.format_string, s).strip(fill))
            return strat

        # Floats
        strat = st.floats(allow_nan=False, allow_infinity=False)
        # f formats can produce very long strings, not good
        if self.kind == "f":
            # threshold can be adjusted
            strat = strat.filter(lambda x: abs(x) < 1e5)
        # take precision into account
        strat = strat.map(lambda x: float(form(self.precision_str + self.kind, x)))
        # truncation can push a very high number above float limit
        strat = strat.filter(lambda x: math.isfinite(x))
        return strat


class StFormat:
    """Store format-related strategies."""

    @classmethod
    def align(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(["", "<", ">", "=", "^"])

    @classmethod
    def sign(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(["", "+", "-", " "])

    @classmethod
    def alt(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(["", "#"])

    @classmethod
    def zero(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(["", "0"])

    @classmethod
    def grouping(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(["", ",", "_"])

    @classmethod
    def width(cls) -> st.SearchStrategy[int | None]:
        return st.one_of(st.none(), st.integers(0, 32))

    @classmethod
    def precision(cls) -> st.SearchStrategy[int | None]:
        return st.one_of(st.none(), st.integers(0, 32))

    @classmethod
    def fill(
        cls, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy[str]:
        """Strategy for fill characters.

        '{}' characters are excluded to avoid format-calls issues. Other characters are
        excluded using :func:`build_exclude`.
        """
        exclude = build_exclude(set("{}"), for_pattern, for_filename)
        alph = st.characters(
            exclude_categories=["Cc", "Cs"],
            exclude_characters=exclude,
        )
        return st.text(alphabet=alph, min_size=0, max_size=1)

    @classmethod
    def format(
        cls,
        kind: str = "sdfeE",
        safe: bool = True,
        for_pattern: bool = False,
        for_filename: bool = False,
    ) -> st.SearchStrategy[FormatSpecs]:
        """Generate a full format string.

        Parameters
        ----------
        kind
            List of types of format to choose from.
        safe
            If True, exclude any format that generate a format error when a Format
            object is created.
        for_pattern
            If True, make sure the format can be used in a pattern.
        for_filename
            If True, make sure the format can be used in a filename.
        """

        @st.composite
        def comp(draw: Drawer) -> FormatSpecs:
            if len(kind) > 1:
                k = draw(st.sampled_from(kind))
            else:
                k = kind

            to_draw = ["align", "width"]
            if k != "s":
                to_draw += ["sign", "alt", "zero", "grouping"]
                if k in "feE":
                    to_draw.append("precision")

            fill = draw(cls.fill(for_pattern=for_pattern, for_filename=for_filename))

            f = FormatSpecs(
                kind=k,
                fill=fill,
                **{spec: draw(getattr(cls, spec)()) for spec in to_draw},
            )
            return f

        strat = comp()

        if safe:
            strat = strat.filter(lambda fmt: fmt.is_valid())

        return strat

    @classmethod
    def value(
        cls,
        st_specs: st.SearchStrategy[FormatSpecs],
        for_pattern: bool = False,
        for_filename: bool = False,
    ) -> st.SearchStrategy[t.Any]:
        """Return strategy for value corresponding to a given format-specs strategy."""

        @st.composite
        def strat(draw: Drawer) -> t.Any:
            specs = draw(st_specs)
            strat = specs.get_value_strategy(
                for_pattern=for_pattern, for_filename=for_filename
            )
            return draw(strat)

        return strat()

    @classmethod
    def format_and_value(
        cls,
        kind: str = "sdfeE",
        safe: bool = True,
        for_pattern: bool = False,
        for_filename: bool = False,
    ) -> tuple[st.SearchStrategy[FormatSpecs], st.SearchStrategy[t.Any]]:
        """Return a strategy for a format and the corresponding value strategy."""
        specs = st.shared(
            cls.format(
                kind=kind, safe=safe, for_pattern=for_pattern, for_filename=for_filename
            )
        )
        value = cls.value(specs, for_pattern=for_pattern, for_filename=for_filename)
        return specs, value


@dataclass
class GroupSpecs:
    """Store group specs and generate a definition."""

    name: str = ""
    """Group name."""
    fmt: str = ""
    """Format spec."""
    fmt_struct: FormatSpecs | None = None
    """Corresponding format specs. None if not format spec is given."""
    rgx: str = ""
    """Regex spec."""
    bool_elts: tuple[str, str] = ("", "")
    """Bool elements of a bool spec."""
    opt: bool = False
    """Option flag."""
    discard: bool = False
    """Discard flag."""
    ordered_specs: list[str] = field(default_factory=lambda: [])
    """List of specs and flags received, in order."""

    def __str__(self) -> str:
        try:
            return self.definition
        except Exception:
            return super().__str__()

    def __contains__(self, key: str) -> bool:
        return key in self.ordered_specs

    def is_valid(self) -> bool:
        """Return if Group object can be constructed."""
        try:
            Group(self.definition, 0)
        except Exception:
            return False
        return True

    @property
    def definition(self) -> str:
        """Return string definition of group, as would be given by user."""
        out = self.name
        for spec in self.ordered_specs:
            value = getattr(self, spec)
            if spec in ["fmt", "rgx"]:
                out += f":{spec}={value}"
            elif spec in ["opt", "discard"]:
                out += f":{spec}"
            elif spec == "bool_elts":
                a, b = value
                out += f":bool={a}:{b}"
            else:
                raise ValueError(f"Unknown spec '{spec}'")

        return out

    def get_value_strategy(
        self, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy:
        """Return strategy of appropriate values for this group."""
        if "rgx" in self:
            exclude = build_exclude(for_pattern=for_pattern, for_filename=for_filename)
            alphabet = st.characters(
                max_codepoint=MAX_CODEPOINT,
                exclude_categories=["C"],
                exclude_characters=exclude,
            )
            strat = st.from_regex(self.rgx, fullmatch=True, alphabet=alphabet)
            strat = strat.filter(lambda s: len(s) < MAX_TEXT_SIZE)
            strat = strat.map(lambda s: s.strip())
            strat = strat.filter(lambda s: re.fullmatch(self.rgx, s))
            return strat

        if "bool_elts" in self:
            return st.booleans()
        if "fmt" in self and self.fmt_struct is not None:
            return self.fmt_struct.get_value_strategy(
                for_pattern=for_pattern, for_filename=for_filename
            )
        raise RuntimeError(
            "Group definition should contain at least rgx, bool, or fmt."
        )

    def get_value_str(self, value: t.Any) -> str:
        """Format value into string.

        Take rgx, bool and fmt specs into account.
        """
        if "rgx" in self:
            return value
        if "bool_elts" in self:
            return self.bool_elts[not value]
        if "fmt" in self:
            return form(self.fmt, value)
        return ""


@dataclass
class GroupValue(GroupSpecs):
    """Store group specs and one accompanying value."""

    value: t.Any = None

    @property
    def value_str(self) -> str:
        """Formatted value."""
        return self.get_value_str(self.value)


@dataclass
class GroupValues(GroupSpecs):
    """Store group specs and multiple accompanying values."""

    values: list[t.Any] = field(default_factory=list)

    @property
    def values_str(self) -> list[str]:
        """Formatted values."""
        return [self.get_value_str(v) for v in self.values]


G = t.TypeVar("G", bound=GroupSpecs)


class StGroup:
    """Store group related strategies."""

    @classmethod
    def name(cls, parsable: bool = False) -> st.SearchStrategy[str]:
        """Strategy for group name.

        If parsable is True, exclude group defaults names (this generator has no
        knowledge of them).
        """
        strat = st.text(
            alphabet=st.characters(
                exclude_categories=["C"],
                exclude_characters=["(", ")", ":"],
                max_codepoint=MAX_CODEPOINT,
            ),
            min_size=1,
            max_size=MAX_TEXT_SIZE,
        )
        if parsable:
            strat = strat.filter(lambda s: s not in Group.DEFAULT_GROUPS)
        return strat

    @classmethod
    def rgx(cls, for_filename: bool = False) -> st.SearchStrategy[str]:
        r"""Choose a valid regex.

        Some special characters are excluded:

        * ^, $, \A and \Z (start and end of string)
        * parenthesis to avoid unbalanced group definition
        * percent to avoid regex replacement (this is tested separately)
        * forward slash
        * double backslash for windows compatibility
        """

        def is_valid(rgx: str) -> bool:
            try:
                re.compile(rgx)
            except Exception:
                return False
            return True

        exclude = build_exclude(
            set(r"()%^$\A\Z"), for_pattern=True, for_filename=for_filename
        )
        strat = (
            st.text(
                alphabet=st.characters(
                    max_codepoint=MAX_CODEPOINT,
                    exclude_categories=["C"],
                    exclude_characters=exclude,
                ),
                min_size=1,
                max_size=MAX_TEXT_SIZE,
            )
            .filter(lambda rgx: r"\\" not in rgx)
            .filter(lambda rgx: is_valid(rgx))
        )

        return strat

    @classmethod
    def fmt(
        cls, kind: str = "sdfeE", for_filename: bool = False
    ) -> st.SearchStrategy[FormatSpecs]:
        """Choose a valid format."""
        return StFormat.format(kind=kind, for_pattern=True, for_filename=for_filename)

    @classmethod
    def bool_elts(
        cls, for_filename: bool = False, allow_empty: bool = True
    ) -> st.SearchStrategy[tuple[str, str]]:
        """Choose two valid strings. The first one is not empty.

        Parameters
        ----------
        allow_empty
            True will allow the second element to be empty. An empty element can
            create ambiguous situations in tests, it won't be allowed in groups and
            patterns.
        """
        exclude = build_exclude(set(":/"), for_pattern=True, for_filename=for_filename)
        alphabet = st.characters(
            exclude_characters=exclude,
            exclude_categories=["C"],
            max_codepoint=MAX_CODEPOINT,
        )

        kwargs: dict[str, t.Any] = dict(alphabet=alphabet, max_size=MAX_TEXT_SIZE)

        @st.composite
        def strat(draw: Drawer) -> tuple[str, str]:
            strat_a = st.text(min_size=1, **kwargs)
            strat_b = st.text(min_size=0 if allow_empty else 1, **kwargs)
            a = draw(strat_a)
            b = draw(strat_b.filter(lambda x: x != a))
            return a, b

        return strat()

    @classmethod
    def opt(cls) -> st.SearchStrategy[bool]:
        return st.just(True)

    @classmethod
    def discard(cls) -> st.SearchStrategy[bool]:
        return st.just(True)

    @classmethod
    def _group(
        cls,
        group_type: type[G],
        ignore: abc.Sequence[str] | None = None,
        fmt_kind: str = "sdfeE",
        parsable: bool = False,
        for_filename: bool = False,
    ) -> st.SearchStrategy[G]:
        if ignore is None:
            ignore = []
        specs = set(["fmt", "rgx", "bool_elts"]) - set(ignore)
        if not specs:
            raise ValueError("Not all fmt, rgx, and bool_elts can be ignored.")

        flags = set(["opt", "discard"]) - set(ignore)

        if parsable:
            fmt_kind = fmt_kind.replace("s", "")

        @st.composite
        def strat(draw: Drawer, fmt_kind: str):
            # select the specs to use
            spec_strat = st.lists(
                st.sampled_from(list(specs)),
                unique=True,
                min_size=1,
                max_size=len(specs),
            )

            chosen = draw(spec_strat)

            if parsable:
                # There is no guarantee that the rgx is compatible with values
                # chosen and formatted by bool or fmt.
                if "rgx" in chosen and ("fmt" in chosen or "bool_elts" in chosen):
                    chosen.remove("rgx")

            if flags:
                chosen += draw(
                    st.lists(
                        st.sampled_from(list(flags)),
                        unique=True,
                        min_size=0,
                        max_size=len(flags),
                    )
                )

            args: dict[str, t.Any] = {}
            args["name"] = draw(cls.name(parsable=parsable))

            # Randomize order
            chosen_ordered = draw(st.permutations(chosen))
            to_draw = list(chosen_ordered)
            # We need to draw some by hand
            if "fmt" in chosen:
                args["fmt_struct"] = draw(
                    cls.fmt(kind=fmt_kind, for_filename=for_filename)
                )
                args["fmt"] = args["fmt_struct"].format_string
                to_draw.remove("fmt")

            if "bool_elts" in chosen:
                args["bool_elts"] = draw(
                    cls.bool_elts(for_filename=for_filename, allow_empty=False)
                )
                to_draw.remove("bool_elts")

            if "rgx" in chosen:
                args["rgx"] = draw(cls.rgx(for_filename=for_filename))
                to_draw.remove("rgx")

            for spec in to_draw:
                args[spec] = draw(getattr(cls, spec)())

            return group_type(**args, ordered_specs=chosen_ordered)

        return strat(fmt_kind)

    @classmethod
    def group(cls, **kwargs) -> st.SearchStrategy[GroupValue]:
        """Generate group structure.

        Specs (fmt, rgx, bool, opt, discard) are put in any order, and not necessarily
        drawn.

        Parameters
        ----------
        ignore
            List of specs to not draw
        fmt_kind
            Kinds of format to generate.
        parsable:
            If true, group is made to be able to generate a value and parse it back.
            Spec `rgx` is removed if `bool` or `fmt` is present. No format of type 's'
            is generated.
        """
        return cls._group(GroupValue, **kwargs)

    @classmethod
    def group_value(
        cls,
        for_filename: bool = False,
        **kwargs,
    ) -> st.SearchStrategy[GroupValue]:
        @st.composite
        def strat(draw: Drawer) -> GroupValue:
            specs = draw(cls._group(GroupValue, for_filename=for_filename, **kwargs))
            value = draw(specs.get_value_strategy(for_filename=for_filename))
            specs.value = value
            return specs

        return strat()

    @classmethod
    def group_values(
        cls, for_filename: bool = False, **kwargs
    ) -> st.SearchStrategy[GroupValues]:
        @st.composite
        def strat(draw: Drawer) -> GroupValues:
            specs = draw(cls._group(GroupValues, for_filename=for_filename, **kwargs))
            values = draw(
                st.lists(
                    specs.get_value_strategy(for_filename=for_filename),
                    min_size=1,
                    unique=True,
                )
            )
            specs.values = values
            return specs

        return strat()


@dataclass
class PatternSpecs:
    """Store information on a full pattern."""

    segments: list[str]
    groups: abc.Sequence[GroupSpecs]

    @property
    def pattern(self) -> str:
        """Return the pattern string."""
        return "".join(self.segments)


@dataclass
class PatternValue(PatternSpecs):
    """Store information on a full pattern. Each group hold one value."""

    groups: abc.Sequence[GroupValue]

    @property
    def filename(self) -> str:
        """Return a filename using the formatted value."""
        segments = self.segments.copy()
        for i, grp in enumerate(self.groups):
            segments[2 * i + 1] = grp.value_str
        return "".join(segments).replace("/", os.sep)


@dataclass
class PatternValues(PatternSpecs):
    """Store information on a full pattern. Each group hold multiple values."""

    groups: abc.Sequence[GroupValues]

    @property
    def filenames(self) -> abc.Iterator[str]:
        """Return a list of filenames using the formatted values."""
        segments = self.segments.copy()

        for values_str in itertools.product(*[grp.values_str for grp in self.groups]):
            for i, seg in enumerate(values_str):
                segments[2 * i + 1] = seg
            yield "".join(segments).replace("/", os.sep)


P = t.TypeVar("P", bound=PatternSpecs)


class StPattern:
    """Strategies related to pattern."""

    max_group: int = 4

    @classmethod
    def _pattern(
        cls,
        st_groupspecs: st.SearchStrategy[G],
        pattern_type: type[P],
        min_group: int = 0,
        separate: bool = True,
        for_filename: bool = False,
    ):
        @st.composite
        def strat(draw: Drawer) -> P:
            groups = draw(
                st.lists(st_groupspecs, min_size=min_group, max_size=cls.max_group)
            )

            # Do not allow fill characters in the pattern
            fills = set()
            for grp in groups:
                if "fmt" in grp.ordered_specs:
                    fmt = grp.fmt_struct
                    assert fmt is not None
                    if fmt.width is not None:
                        if fmt.fill == "":
                            fills.add(" ")
                        else:
                            fills.add(fmt.fill)

            exclude = build_exclude(fills, for_pattern=True, for_filename=for_filename)
            # authorize folder separator in segments
            exclude.discard("/")
            text = st.text(
                alphabet=st.characters(
                    max_codepoint=MAX_CODEPOINT,
                    exclude_categories=["C", "Nd"],
                    exclude_characters=exclude,
                ),
                min_size=1 if separate else 0,
                max_size=MAX_TEXT_SIZE,
            )
            # no consecutive folder separator
            consecutive_sep = re.compile("//")
            text = text.map(lambda s: consecutive_sep.sub("/", s))

            segments = ["" for _ in range(2 * len(groups) + 1)]
            if len(groups) > 0:
                segments[1::2] = [f"%({g.definition})" for g in groups]
                ends = text.filter(
                    lambda s: not s.startswith("/") and not s.endswith("/")
                )
                segments[0] = draw(ends)
                segments[-1] = draw(ends)

            if len(groups) > 1:
                segments[2:-2:2] = [draw(text) for _ in range(len(groups) - 1)]

            return pattern_type(segments=segments, groups=groups)

        return strat()

    @classmethod
    def pattern(
        cls,
        min_group: int = 0,
        separate: bool = True,
        for_filename: bool = False,
        **kwargs,
    ) -> st.SearchStrategy[PatternSpecs]:
        """Generate a pattern structure.

        Each pattern comes with fixing values and strings for each group. (should be
        moved in a composite function with a pattern argument).
        Values are passed through the format to avoid issues with precision.

        There are some limitations:

        * If argument `separate` is true, groups are separated by at least one
          character, this is to avoid some ambiguous cases like two consecutive
          integers for instance (it can be impossible to correctly separate the two).

        Parameters
        ----------
        min_group
            Minimum number of groups in pattern. Default is zero.
        separate
            If True, groups are separated by at least one character in the pattern.
        kwargs
            Passed to StGroup strategy.
        """
        return cls._pattern(
            StGroup.group(for_filename=for_filename, **kwargs),
            PatternSpecs,
            min_group=min_group,
            separate=separate,
            for_filename=for_filename,
        )

    @classmethod
    def pattern_value(
        cls,
        min_group: int = 0,
        separate: bool = True,
        for_filename: bool = False,
        **kwargs,
    ) -> st.SearchStrategy[PatternValue]:
        return cls._pattern(
            StGroup.group_value(for_filename=for_filename, **kwargs),
            PatternValue,
            min_group=min_group,
            separate=separate,
            for_filename=for_filename,
        )

    @classmethod
    def pattern_values(
        cls,
        min_group: int = 0,
        separate: bool = True,
        for_filename: bool = False,
        **kwargs,
    ) -> st.SearchStrategy[PatternValues]:
        strat = cls._pattern(
            StGroup.group_values(for_filename=for_filename, **kwargs),
            PatternValues,
            min_group=min_group,
            separate=separate,
            for_filename=for_filename,
        )

        def filter_duplicate_filenames(pattern: PatternValues) -> bool:
            filenames = list(pattern.filenames)
            return len(filenames) == len(set(filenames))

        strat = strat.filter(filter_duplicate_filenames)
        return strat


@st.composite
def time_segments(draw) -> list[str]:
    """Generate pattern segments with date elements."""
    names = draw(
        st.lists(
            st.sampled_from(datetime_keys),
            min_size=1,
            max_size=len(datetime_keys),
        )
    )

    text = st.text(
        alphabet=st.characters(
            max_codepoint=MAX_CODEPOINT,
            exclude_categories=["C"],
            exclude_characters=set("%()\\") | FORBIDDEN_CHAR,
        ),
        min_size=0,
        max_size=MAX_TEXT_SIZE,
    )

    segments = ["" for _ in range(2 * len(names) + 1)]
    segments[1::2] = names
    for i in range(len(names) + 1):
        segments[2 * i] = draw(text)

    for n_seg, seg in enumerate(segments[1::2]):
        # force non-alphabetic char after or before written month name
        i = n_seg * 2 + 1
        if seg == "B":
            for j in [i - 1, i + 1]:
                if segments[j].isalpha() or not segments[j]:
                    segments[j] = "_"

    return segments
