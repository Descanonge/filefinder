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
MAX_TEXT_SIZE = 32

if sys.platform in ["win32", "cygwin"]:
    FORBIDDEN_CHAR = set('<>:"\\|?')
elif sys.platform == "darwin":
    FORBIDDEN_CHAR = set(":")
else:
    FORBIDDEN_CHAR = set()


def form(fmt: str, value: t.Any) -> str:
    return f"{{:{fmt}}}".format(value)


def build_exclude(
    exclude: set[str] | None = None,
    for_pattern: bool = False,
    for_filename: bool = False,
) -> set[str]:
    if exclude is None:
        exclude = set()
    if for_pattern:
        exclude |= set("%()")
    if for_filename:
        exclude |= FORBIDDEN_CHAR
    return exclude


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
        return self.format_string

    @property
    def width_str(self) -> str:
        return "" if self.width is None else f"{self.width:d}"

    @property
    def precision_str(self) -> str:
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
        try:
            Format(self.format_string)
        except FormatError:
            return False
        return True

    def get_value_strategy(
        self, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy[str | int | float]:
        strat: st.SearchStrategy

        if self.kind == "d":
            return st.integers()

        if self.kind == "s":
            exclude = build_exclude(for_pattern=for_pattern, for_filename=for_filename)
            strat = st.text(
                alphabet=st.characters(
                    max_codepoint=MAX_CODEPOINT,
                    exclude_categories=["C"],
                    exclude_characters=exclude,
                ),
                max_size=MAX_TEXT_SIZE,
            )
            fill = self.fill if self.fill and self.align else " "
            strat = strat.map(lambda s: form(self.format_string, s).strip(fill))
            return strat

        # Floats
        strat = st.floats(allow_nan=False, allow_infinity=False)
        # take precision into account
        strat = strat.map(lambda x: float(form(self.precision_str + self.kind, x)))
        # truncation can push a very high number above float limit
        strat = strat.filter(lambda x: math.isfinite(x))
        return strat


@dataclass
class FormatValue:
    struct: StructFormat
    value: t.Any

    def __iter__(self):
        return iter([self.struct, self.value])


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
    def fill(
        cls, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy[str]:
        """Fill characters.

        Some characters are excluded to avoid problems:

        * {} for format calls
        * () for group definitions
        * /  for file scanning.
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
        safe: bool = False,
        for_pattern: bool = False,
        for_filename: bool = False,
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
            strat = strat.filter(lambda fmt: fmt.is_valid())

        return strat

    @classmethod
    def format_value(cls, **kwargs) -> st.SearchStrategy[FormatValue]:
        @st.composite
        def comp(draw) -> FormatValue:
            struct = draw(cls.format(**kwargs))
            value = draw(struct.get_value_strategy())
            return FormatValue(struct, value)

        return comp()


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

    def get_value_strategy(
        self, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy:
        if "rgx" in self:
            return st.from_regex(self.rgx, fullmatch=True)
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
        if "rgx" in self:
            return value
        if "bool_elts" in self:
            return self.bool_elts[not value]
        if "fmt" in self:
            return form(self.fmt, value)
        return ""


@dataclass
class GroupValue:
    struct: StructGroup
    value: t.Any

    def __iter__(self):
        return iter([self.struct, self.value])

    @property
    def value_str(self) -> str:
        return self.struct.get_value_str(self.value)


@dataclass
class GroupValues:
    struct: StructGroup
    values: list[t.Any]

    @property
    def values_str(self) -> list[str]:
        return [self.struct.get_value_str(v) for v in self.values]


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
            max_size=MAX_TEXT_SIZE,
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
                max_size=MAX_TEXT_SIZE,
            )
            .filter(lambda rgx: r"\\" not in rgx)
            .filter(lambda rgx: is_valid(rgx))
        )

        return strat

    @classmethod
    def fmt(
        cls, kind: str = "sdfeE", for_filename: bool = False
    ) -> st.SearchStrategy[StructFormat]:
        """Choose a valid format."""
        return StFormat.format(
            safe=True, kind=kind, for_pattern=True, for_filename=for_filename
        )

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
            a = draw(st.text(alphabet=alphabet, min_size=1, max_size=MAX_TEXT_SIZE))
            b = draw(st.text(alphabet=alphabet, max_size=MAX_TEXT_SIZE))
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
        for_filename: bool = False,
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
        specs = set(["fmt", "rgx", "bool_elts"]) - set(ignore)
        if not specs:
            raise ValueError("Not all fmt, rgx, and bool_elts can be ignored.")

        flags = set(["opt", "discard"]) - set(ignore)

        @st.composite
        def comp(draw, fmt_kind: str):
            # select the specs to use
            spec_strat = st.lists(
                st.sampled_from(list(specs)),
                unique=True,
                min_size=1,
                max_size=len(specs),
            )

            chosen = draw(spec_strat)
            if flags:
                chosen += draw(
                    st.lists(
                        st.sampled_from(list(flags)), unique=True, max_size=len(flags)
                    )
                )

            args = {}
            args["name"] = draw(cls.name())

            if parsable and "rgx" in chosen:
                if "bool_elts" in chosen or "fmt" in chosen:
                    chosen.remove("rgx")
            if "fmt" in chosen:
                args["fmt_struct"] = draw(cls.fmt(kind=fmt_kind))
                args["fmt"] = args["fmt_struct"].format_string
            for spec in chosen:
                if spec == "fmt":
                    continue
                args[spec] = draw(getattr(cls, spec)())

            return StructGroup(**args, ordered_specs=chosen)

        return comp(fmt_kind)

    @classmethod
    def group_value(cls, **kwargs) -> st.SearchStrategy[GroupValue]:
        @st.composite
        def comp(draw):
            struct = draw(cls.group(**kwargs))
            value = draw(struct.get_value_strategy())

            return GroupValue(struct, value)

        return comp()

    @classmethod
    def group_values(cls, **kwargs) -> st.SearchStrategy[GroupValue]:
        @st.composite
        def comp(draw):
            struct = draw(cls.group(**kwargs))
            values = draw(
                st.lists(struct.get_value_strategy(), min_size=1, unique=True)
            )
            return GroupValues(struct, values)

        return comp()


@dataclass
class StructPattern:
    segments: list[str]
    groups: list[StructGroup]

    @property
    def pattern(self) -> str:
        """Return the pattern string."""
        return "".join(self.segments)


@dataclass
class PatternValue:
    pattern: StructPattern
    value: list[GroupValue]

    @property
    def filename(self) -> str:
        """Return a filename using the formatted value."""
        segments = self.pattern.segments.copy()
        for i, grp in enumerate(self.value):
            segments[2 * i + 1] = grp.value_str
        return "".join(segments).replace("/", os.sep)


@dataclass
class PatternValues:
    pattern: StructPattern
    values: list[GroupValues]

    @property
    def filenames(self) -> abc.Iterator[str]:
        """Return a list of filenames using the formatted values."""
        segments = self.pattern.segments.copy()

        for values_str in itertools.product(*[grp.values_str for grp in self.values]):
            for i, seg in enumerate(values_str):
                segments[2 * i + 1] = seg
            yield "".join(segments).replace("/", os.sep)


class StPattern:
    """Strategies related to pattern."""

    max_group: int = 4

    @classmethod
    def draw_segments(
        cls, draw: abc.Callable, groups: list[StructGroup], separate: bool
    ):
        text = st.text(
            alphabet=st.characters(
                max_codepoint=MAX_CODEPOINT,
                exclude_categories=["C"],
                exclude_characters=set("%()\\") | FORBIDDEN_CHAR,
            ),
            min_size=1 if separate else 0,
            max_size=MAX_TEXT_SIZE,
        )

        segments = ["" for _ in range(2 * len(groups) + 1)]
        if len(groups) == 0:
            return segments

        segments[1::2] = [f"%({g.definition})" for g in groups]
        ends = text.filter(lambda s: not s.startswith("/") and not s.endswith("/"))
        segments[0] = draw(ends)
        segments[-1] = draw(ends)

        if len(groups) > 1:
            segments[2:-2:2] = [draw(text) for _ in range(len(groups) - 1)]

        return segments

    @classmethod
    def draw_groups(
        cls,
        draw: abc.Callable,
        strategy: abc.Callable[..., st.SearchStrategy],
        min_group: int,
        **kwargs,
    ):
        groups = st.lists(
            strategy(**kwargs), min_size=min_group, max_size=cls.max_group
        )
        return draw(groups)

    @classmethod
    def pattern(
        cls, min_group: int = 0, separate: bool = True, **kwargs
    ) -> st.SearchStrategy[StructPattern]:
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

        @st.composite
        def comp(draw) -> StructPattern:
            groups: list[StructGroup] = cls.draw_groups(
                draw, StGroup.group, min_group, **kwargs
            )
            segments = cls.draw_segments(draw, groups, separate)
            return StructPattern(segments=segments, groups=groups)

        return comp()

    @classmethod
    def pattern_value(
        cls, min_group: int = 0, separate: bool = True, **kwargs
    ) -> st.SearchStrategy[PatternValue]:
        @st.composite
        def comp(draw) -> PatternValue:
            groups_val: list[GroupValue] = cls.draw_groups(
                draw, StGroup.group_value, min_group, **kwargs
            )
            groups = [g.struct for g in groups_val]
            segments = cls.draw_segments(draw, groups, separate)
            pattern = StructPattern(segments=segments, groups=groups)
            return PatternValue(pattern=pattern, value=groups_val)

        return comp()

    @classmethod
    def pattern_values(
        cls, min_group: int = 0, separate: bool = True, **kwargs
    ) -> st.SearchStrategy[PatternValues]:
        @st.composite
        def comp(draw) -> PatternValues:
            groups_val: list[GroupValues] = cls.draw_groups(
                draw, StGroup.group_values, min_group, **kwargs
            )
            groups = [g.struct for g in groups_val]
            segments = cls.draw_segments(draw, groups, separate)
            pattern = StructPattern(segments=segments, groups=groups)
            return PatternValues(pattern=pattern, values=groups_val)

        return comp()
