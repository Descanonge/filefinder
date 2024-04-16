"""Generation of parameters."""

import itertools
import math
import os
import re
import sys
import typing as t
from collections import abc
from dataclasses import dataclass, field

from filefinder.format import Format, FormatError
from filefinder.group import Group
from hypothesis import strategies as st

MAX_CODEPOINT = 1024

if sys.platform in ["win32", "cygwin"]:
    FORBIDDEN_CHAR = set('<>:"\\|?')
elif sys.platform == "darwin":
    FORBIDDEN_CHAR = set(":")
else:
    FORBIDDEN_CHAR = set()


def form(fmt: str, value: t.Any) -> str:
    return f"{{:{fmt}}}".format(value)


class FormatChoices:
    """List of possible values for format specs."""

    align = ["", "<", ">", "=", "^"]
    sign = ["" "+", "-", " "]
    alt = ["", "#"]
    zero = ["" "0"]
    grouping = ["", ",", "_"]


@dataclass
class StructFormat:
    """Store formt specs and generate format string."""

    align: str = ""
    fill: str = ""
    sign: str = ""
    alt: str = ""
    zero: str = ""
    grouping: str = ""
    width: int | None = None
    precision: int | None = None
    kind: str = "s"

    def __str__(self) -> str:
        return self.fmt

    @property
    def width_str(self) -> str:
        return "" if self.width is None else f"{self.width:d}"

    @property
    def precision_str(self) -> str:
        return "" if self.precision is None else f".{self.precision:d}"

    @property
    def fmt(self) -> str:
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


class StFormat:
    """Store format-related strategies."""

    @classmethod
    def align(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(FormatChoices.align)

    @classmethod
    def sign(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(FormatChoices.sign)

    @classmethod
    def alt(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(FormatChoices.alt)

    @classmethod
    def zero(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(FormatChoices.zero)

    @classmethod
    def grouping(cls) -> st.SearchStrategy[str]:
        return st.sampled_from(FormatChoices.grouping)

    @classmethod
    def width(cls) -> st.SearchStrategy[int | None]:
        return st.one_of(st.none(), st.integers(0, 32))

    @classmethod
    def precision(cls) -> st.SearchStrategy[int | None]:
        return st.one_of(st.none(), st.integers(0, 32))

    @classmethod
    def fill(cls) -> st.SearchStrategy[str]:
        """Fill characters.

        Some characters are excluded to avoid problems:

        * {} for format calls
        * () for group definitions
        * /  for file scanning.
        """
        alph = st.characters(
            exclude_categories=["Cc", "Cs"],
            exclude_characters=set("{}()/\\") | FORBIDDEN_CHAR,
        )
        return st.text(alphabet=alph, min_size=0, max_size=1)

    @staticmethod
    def filter_bad(fmt: StructFormat) -> bool:
        """Filter out erroneous or dangerous format strings."""
        try:
            Format(fmt.fmt)
        except FormatError:
            return False
        return True

    @classmethod
    def format(
        cls, kind: str = "sdfeE", safe: bool = False
    ) -> st.SearchStrategy[StructFormat]:
        """Generate a format.

        Parameters
        ----------
        kind
            Type of format is chosen from those listed in this parameter.
        safe
            Exclude any format that generate a format error when a Format object is
            created.
        """

        @st.composite
        def comp(draw) -> StructFormat:
            if len(kind) > 1:
                k = draw(st.sampled_from(kind))
            else:
                k = kind

            to_draw = ["align", "fill", "width"]
            if k != "s":
                to_draw += ["sign", "alt", "zero", "grouping"]
                if k in "feE":
                    to_draw.append("precision")

            f = StructFormat(
                kind=k, **{spec: draw(getattr(cls, spec)()) for spec in to_draw}
            )
            return f

        strat = comp()

        if safe:
            strat = strat.filter(cls.filter_bad)

        return strat

    @classmethod
    def loop_over(
        cls, ignore: abc.Sequence[str] | None = None, **kwargs
    ) -> abc.Iterator[StructFormat]:
        """Generate formats with every possible specs.

        Parameters
        ----------
        ignore
            Sequence of specs to not loop over.
        kwargs
            Passed to StructFormat init.
        """
        to_loop = ["align", "sign", "alt", "zero", "grouping"]
        if ignore is None:
            ignore = []
        for name in ignore:
            to_loop.remove(name)

        iterables = [getattr(FormatChoices, spec) for spec in to_loop]
        for specs in itertools.product(*iterables):
            kw = kwargs | dict(zip(to_loop, specs))
            yield StructFormat(**kw)


@dataclass
class StructGroup:
    """Store group specs and generate a definition."""

    name: str = ""
    fmt: str = ""
    fmt_struct: StructFormat | None = None
    rgx: str = ""
    bool_elts: tuple[str, str] = ("", "")
    opt: bool = False
    discard: bool = False
    ordered_specs: list[str] = field(default_factory=lambda: [])

    def __str__(self) -> str:
        try:
            return self.definition
        except Exception:
            return super().__str__()

    def __contains__(self, key: str) -> bool:
        return key in self.ordered_specs

    def is_valid(self) -> bool:
        try:
            Group(self.definition, 0)
        except Exception:
            return False
        return True

    @property
    def definition(self) -> str:
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

    @property
    def strategy_value(self) -> st.SearchStrategy:
        if "rgx" in self:
            return st.from_regex(self.rgx, fullmatch=True)
        if "bool_elts" in self:
            return st.booleans()
        if "fmt" in self and self.fmt_struct is not None:
            fmt = self.fmt_struct
            if fmt.kind == "s":
                exclude = set("()/") | FORBIDDEN_CHAR
                fill = fmt.fill if fmt.fill and fmt.align else " "
                exclude.add(fill)
                return st.text(
                    alphabet=st.characters(
                        max_codepoint=MAX_CODEPOINT,
                        exclude_categories=["C"],
                        exclude_characters=exclude,
                    )
                ).map(lambda s: form(self.fmt, s).strip(fill))
            if fmt.kind == "d":
                return st.integers()
            if fmt.kind in "feE":
                precision = "" if fmt.precision is None else f".{fmt.precision}"
                strat = st.floats(allow_infinity=False, allow_nan=False)
                strat = strat.map(lambda x: float(form(f"{precision}{fmt.kind}", x)))
                # sometimes a truncation can push a very high number above float limit
                strat = strat.filter(lambda x: math.isfinite(x))
                return strat
        return st.none()

    def get_value_str(self, value: t.Any) -> str:
        if "rgx" in self:
            return value
        if "bool_elts" in self:
            return self.bool_elts[not value]
        if "fmt" in self:
            return form(self.fmt, value)
        return ""


class StGroup:
    """Store group related strategies."""

    @classmethod
    def name(cls) -> st.SearchStrategy[str]:
        return st.text(
            alphabet=st.characters(
                exclude_categories=["C"],
                exclude_characters=["(", ")", ":"],
                max_codepoint=MAX_CODEPOINT,
            ),
            min_size=1,
        )

    @classmethod
    def rgx(cls) -> st.SearchStrategy[str]:
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

        strat = (
            st.text(
                alphabet=st.characters(
                    max_codepoint=MAX_CODEPOINT,
                    exclude_categories=["C"],
                    exclude_characters=list(r"()/%^$\A\Z"),
                ),
                min_size=1,
            )
            .filter(lambda rgx: r"\\" not in rgx)
            .filter(lambda rgx: is_valid(rgx))
        )

        return strat

    @classmethod
    def fmt(cls, kind: str = "sdfeE") -> st.SearchStrategy[StructFormat]:
        """Choose a valid format."""
        return StFormat.format(safe=True, kind=kind)

    @classmethod
    def bool_elts(cls) -> st.SearchStrategy[tuple[str, str]]:
        """Choose two valid strings. The first one is not empty."""
        alphabet = st.characters(
            exclude_characters=set("():/\\") | FORBIDDEN_CHAR,
            exclude_categories=["C"],
            max_codepoint=MAX_CODEPOINT,
        )

        @st.composite
        def comp(draw) -> tuple[str, str]:
            a = draw(st.text(alphabet=alphabet, min_size=1))
            b = draw(st.text(alphabet=alphabet))
            return a, b

        return comp().filter(lambda ab: ab[0] != ab[1])

    @classmethod
    def opt(cls) -> st.SearchStrategy[bool]:
        return st.just(True)

    @classmethod
    def discard(cls) -> st.SearchStrategy[bool]:
        return st.just(True)

    @classmethod
    def group(
        cls,
        ignore: list[str] | None = None,
        fmt_kind: str = "sdfeE",
        parsable: bool = False,
    ) -> st.SearchStrategy[StructGroup]:
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
            Spec `rgx` is removed if `bool` or `fmt` is present.
        """
        if ignore is None:
            ignore = []
        specs = set(["fmt", "rgx", "bool_elts", "opt", "discard"])
        specs -= set(ignore)

        # we must have at least one of those
        must_have = set(["fmt", "rgx", "bool_elts"])
        assert specs & must_have

        @st.composite
        def comp(draw, fmt_kind: str):
            # select the specs to use
            spec_strat = st.lists(
                st.sampled_from(list(specs)),
                unique=True,
                min_size=1,
                max_size=len(specs),
            ).filter(lambda x: len(set(x) & must_have) > 0)

            chosen = draw(spec_strat)

            values = {}
            values["name"] = draw(cls.name())

            if parsable and "rgx" in chosen:
                if "bool_elts" in chosen or "fmt" in chosen:
                    chosen.remove("rgx")
            if "fmt" in chosen:
                values["fmt_struct"] = draw(cls.fmt(kind=fmt_kind))
                values["fmt"] = values["fmt_struct"].fmt
            for spec in chosen:
                if spec == "fmt":
                    continue
                values[spec] = draw(getattr(cls, spec)())

            return StructGroup(**values, ordered_specs=chosen)

        return comp(fmt_kind).filter(lambda g: g.is_valid())

    @classmethod
    def group_with_values(
        cls, size: int = 16, **kwargs
    ) -> st.SearchStrategy[tuple[StructGroup, list[t.Any]]]:
        @st.composite
        def comp(draw):
            struct = draw(cls.group(**kwargs))
            values = st.lists(
                struct.strategy_value, min_size=size, max_size=size, unique=True
            )
            return struct, draw(values)

        return comp()


@dataclass
class StructPattern:
    """Store information for Finder pattern."""

    segments: list[str] = field(default_factory=lambda: [])
    """Groups definitions interlaced with fixed filename parts."""
    groups: list[StructGroup] = field(default_factory=lambda: [])
    """List of groups structures in the pattern."""
    values: list[t.Any] = field(default_factory=lambda: [])
    """Values of appropriate type for each group."""
    values_str: list[str] = field(default_factory=lambda: [])
    """Formatted value for each group."""

    multiple_values: list[list[t.Any]] = field(default_factory=lambda: [])
    """Values of appropriate type for each group."""
    multiple_values_str: list[list[str]] = field(default_factory=lambda: [])
    """Formatted value for each group."""

    @property
    def pattern(self) -> str:
        """Return the pattern string."""
        return "".join(self.segments)

    @property
    def filename(self) -> str:
        """Return a filename using the formatted value."""
        segments = self.segments.copy()
        for i, seg in enumerate(self.values_str):
            segments[2 * i + 1] = seg
        return "".join(segments).replace("/", os.sep)

    @property
    def filenames(self) -> abc.Iterator[str]:
        """Return a list of filenames using the formatted values."""
        segments = self.segments.copy()

        for values_str in itertools.product(*self.multiple_values_str):
            for i, seg in enumerate(values_str):
                segments[2 * i + 1] = seg
            yield "".join(segments).replace("/", os.sep)


class StPattern:
    """Strategies related to pattern."""

    max_group: int = 4

    @classmethod
    def pattern(
        cls, min_group: int = 0, separate: bool = True, **kwargs
    ) -> st.SearchStrategy[StructPattern]:
        """Generate a pattern structure.

        Each pattern comes with fixing values and strings for each group. (should be
        moved in a composite function with a pattern argument).
        Values are passed through the format to avoid issues with precision.

        There are some limitations:

        * The name is not one of the default groups.
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

        @st.composite
        def comp(draw) -> StructPattern:
            st_group = StGroup.group(**kwargs).filter(
                lambda g: g.name not in Group.DEFAULT_GROUPS
            )
            groups = draw(
                st.lists(st_group, min_size=min_group, max_size=cls.max_group)
            )
            text = st.text(
                alphabet=st.characters(
                    max_codepoint=MAX_CODEPOINT,
                    exclude_categories=["C"],
                    exclude_characters=set("%()\\") | FORBIDDEN_CHAR,
                ),
                max_size=64,
                min_size=1 if separate else 0,
            )

            segments = ["" for _ in range(2 * len(groups) + 1)]
            segments[1::2] = [f"%({g.definition})" for g in groups]
            segments[::2] = [draw(text) for _ in range(len(groups) + 1)]

            return StructPattern(segments=segments, groups=groups)

        # starting with / is wrong, this gets dropped by the filesystem
        # ending with / is wrong, we are looking for files
        out = comp().filter(
            lambda p: not p.pattern.startswith("/") and not p.pattern.endswith("/")
        )

        return out

    @classmethod
    def pattern_with_values(cls, **kwargs) -> st.SearchStrategy[StructPattern]:
        @st.composite
        def comp(draw) -> StructPattern:
            pattern: StructPattern = draw(cls.pattern(**kwargs))

            values: list[t.Any] = []
            values_str: list[str] = []
            for grp in pattern.groups:
                val = draw(grp.strategy_value)
                values.append(val)
                values_str.append(grp.get_value_str(val))

            pattern.values = values
            pattern.values_str = values_str
            return pattern

        return comp()

    @classmethod
    def pattern_with_multiple_values(cls, **kwargs) -> st.SearchStrategy[StructPattern]:
        @st.composite
        def comp(draw) -> StructPattern:
            pattern: StructPattern = draw(cls.pattern(**kwargs))

            values: list[list[t.Any]] = []
            values_str: list[list[str]] = []
            for grp in pattern.groups:
                val = draw(st.lists(grp.strategy_value, min_size=1))
                values.append(val)
                values_str.append([grp.get_value_str(x) for x in val])

            pattern.multiple_values = values
            pattern.multiple_values_str = values_str
            return pattern

        return comp()
