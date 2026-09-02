"""Group and pattern-related strategies."""

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, TypeVar

import hypothesis.strategies as st
from hypothesis import example

from filefinder.dates import datetime_keys
from filefinder.group import Group

from . import (
    MAX_CODEPOINT,
    MAX_TEXT_SIZE,
    Drawer,
    build_exclude,
    form,
)
from .format_generation import FormatSpecs, StFormat


@dataclass
class GroupSpecs:
    """Store group specs and generate a definition."""

    name: str = ""
    """Group name."""
    fmt: str = ""
    """Format spec."""
    fmt_struct: FormatSpecs | None = None
    """Corresponding format specs. None if no format spec is given."""
    rgx: str = ""
    """Regex spec."""
    bool_elts: tuple[str, str] = ("", "")
    """Bool elements of a bool spec."""
    bool_elts_sep: str = ":"
    """Bool elements separator (either colon or empty)"""
    opt: bool = False
    """Option flag."""
    pre: str = ""
    """Prefix"""
    post: str = ""
    """Suffix"""
    ordered_specs: list[str] = field(default_factory=list)
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

    def get_regex(self, *, matching: bool = False) -> str:
        if "rgx" in self:
            rgx = self.rgx
        elif "bool" in self:
            rgx = "|".join(re.escape(x) for x in self.bool_elts)
        elif "fmt" in self:
            assert self.fmt_struct is not None
            rgx = self.fmt_struct.get_regex(capture=False)
        else:
            raise ValueError("Cannon create regex from specs.")

        if matching:
            rgx = self.pre + rgx + self.post
            if "opt" in self:
                rgx = f"(?:{rgx})?"
            rgx = f"({rgx})"

        return rgx

    @property
    def definition(self) -> str:
        """Return string definition of group, as would be given by user."""
        out = self.name
        for spec in self.ordered_specs:
            if spec in ["fmt", "rgx", "pre", "post"]:
                out += f":{spec}={getattr(self, spec)}"
            elif spec == "opt":
                out += f":{spec}"
            elif spec == "bool":
                a, b = self.bool_elts
                out += f":bool={a}{self.bool_elts_sep}{b}"
            else:
                raise ValueError(f"Unknown spec '{spec}'")

        return out

    def get_value_strategy(
        self, *, for_pattern: bool = False, for_filename: bool = False
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

        if "bool" in self:
            return st.booleans()
        if "fmt" in self and self.fmt_struct is not None:
            return self.fmt_struct.get_value_strategy(
                for_pattern=for_pattern, for_filename=for_filename
            )
        raise RuntimeError(
            "Group definition should contain at least rgx, bool, or fmt."
        )

    def get_value_str(self, value: Any) -> str:
        """Format value into string.

        Take rgx, bool and fmt specs into account.
        """
        if "rgx" in self:
            s = value
        elif "bool" in self:
            s = self.bool_elts[not value]
        elif "fmt" in self:
            s = form(self.fmt, value)
        else:
            raise KeyError()

        return self.pre + s + self.post


@dataclass
class GroupValue(GroupSpecs):
    """Store group specs and one accompanying value."""

    value: Any = None

    @property
    def value_str(self) -> str:
        """Formatted value."""
        return self.get_value_str(self.value)


@dataclass
class GroupValues(GroupSpecs):
    """Store group specs and multiple accompanying values."""

    values: list[Any] = field(default_factory=list)

    @property
    def values_str(self) -> list[str]:
        """Formatted values."""
        return [self.get_value_str(v) for v in self.values]


G = TypeVar("G", bound=GroupSpecs)


class StGroup:
    """Store group related strategies."""

    @classmethod
    def name(cls) -> st.SearchStrategy[str]:
        """Strategy for group name."""
        strat = st.text(
            alphabet=st.characters(
                exclude_categories=["C"],
                exclude_characters=["(", ")", ":"],
                max_codepoint=MAX_CODEPOINT,
            ),
            min_size=1,
            max_size=MAX_TEXT_SIZE,
        )
        strat = strat.filter(lambda s: s not in Group.DATE_GROUPS).filter(
            lambda s: s != "date"
        )
        return strat

    @classmethod
    def rgx(cls, *, for_filename: bool = False) -> st.SearchStrategy[str]:
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
            .filter(is_valid)
        )
        return strat

    @classmethod
    def fmt(
        cls, kind: str = "sdfeE", *, for_filename: bool = False
    ) -> st.SearchStrategy[FormatSpecs]:
        """Choose a valid format."""
        return StFormat.format(kind=kind, for_pattern=True, for_filename=for_filename)

    @classmethod
    def text(
        cls, *, for_filename: bool = False, **kwargs: Any
    ) -> st.SearchStrategy[str]:
        """Text for :bool, :pre and :post."""
        exclude = build_exclude(set(":/"), for_pattern=True, for_filename=for_filename)
        alphabet = st.characters(
            exclude_characters=exclude,
            exclude_categories=["C"],
            max_codepoint=MAX_CODEPOINT,
        )
        reserved_kw = ["fmt", "bool", "rgx", "opt"]

        strat = st.text(alphabet=alphabet, max_size=MAX_TEXT_SIZE, **kwargs)
        strat = strat.filter(lambda s: s not in reserved_kw)
        return strat

    @classmethod
    def bool_elts(
        cls, *, for_filename: bool = False
    ) -> st.SearchStrategy[tuple[str, str]]:
        """Choose two valid strings. The first one is not empty."""
        strat_a = cls.text(for_filename=for_filename, min_size=1)
        strat_b = cls.text(for_filename=for_filename, min_size=0)

        @st.composite
        def strat(draw: Drawer) -> tuple[str, str]:
            a = draw(strat_a)
            b = draw(strat_b.filter(lambda x: x != a))
            return a, b

        return strat()

    @classmethod
    def pre_post(cls, *, for_filename: bool = False) -> st.SearchStrategy[str]:
        return cls.text(for_filename=for_filename, min_size=1)

    @classmethod
    def opt(cls) -> st.SearchStrategy[bool]:
        return st.just(value=True)

    @classmethod
    def _group(
        cls,
        group_type: type[G],
        ignore: Sequence[str] | None = None,
        fmt_kind: str = "sdfeE",
        *,
        parsable: bool = False,
        for_filename: bool = False,
    ) -> st.SearchStrategy[G]:
        if ignore is None:
            ignore = []
        specs = {"fmt", "rgx", "bool"} - set(ignore)
        if not specs:
            raise ValueError("Not all fmt, rgx, and bool can be ignored.")

        flags = {"opt", "pre", "post"} - set(ignore)

        if parsable:
            fmt_kind = fmt_kind.replace("s", "")

        @st.composite
        def strat(draw: Drawer, fmt_kind: str) -> G:
            # select the specs to use
            spec_strat = st.lists(
                st.sampled_from(list(specs)),
                unique=True,
                min_size=1,
                max_size=len(specs),
            )

            chosen = draw(spec_strat)

            if parsable and "rgx" in chosen and ("fmt" in chosen or "bool" in chosen):
                # There is no guarantee that the rgx is compatible with values
                # chosen and formatted by bool or fmt.
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

            args: dict[str, Any] = {}
            args["name"] = draw(cls.name())

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

            if "bool" in chosen:
                args["bool_elts"] = draw(cls.bool_elts(for_filename=for_filename))
                if args["bool_elts"][1]:
                    args["bool_elts_sep"] = ":"
                else:
                    args["bool_elts_sep"] = draw(st.sampled_from(["", ":"]))
                to_draw.remove("bool")

            if "rgx" in chosen:
                args["rgx"] = draw(cls.rgx(for_filename=for_filename))
                to_draw.remove("rgx")

            if "pre" in chosen:
                args["pre"] = draw(cls.pre_post(for_filename=for_filename))
                to_draw.remove("pre")

            if "post" in chosen:
                args["post"] = draw(cls.pre_post(for_filename=for_filename))
                to_draw.remove("post")

            for spec in to_draw:
                args[spec] = draw(getattr(cls, spec)())

            return group_type(**args, ordered_specs=chosen_ordered)

        return strat(fmt_kind)

    @classmethod
    def group(cls, **kwargs: Any) -> st.SearchStrategy[GroupValue]:
        """Generate group structure.

        Specs (fmt, rgx, bool, opt) are put in any order, and not necessarily drawn.

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
        *,
        for_filename: bool = False,
        **kwargs: Any,
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
        cls, *, for_filename: bool = False, **kwargs: Any
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


class GroupSpecsExamples:
    def __init__(self) -> None:
        self.examples: dict[str, GroupSpecs] = {}

    def add(self, definition: str, specs: GroupSpecs, regex: str) -> None:
        assert specs.definition == definition
        assert specs.get_regex() == regex
        self.examples[specs.name] = specs

    def test(self, func: Callable) -> Callable:
        for e in self.examples.values():
            func = example(e)(func)
        return func

    def get_group(self, name: str) -> Group:
        return Group(self.examples[name].definition, 0)


examples = GroupSpecsExamples()


## Format
examples.add(
    "fmt_int:fmt=02d",
    GroupSpecs(
        "fmt_int",
        fmt="02d",
        fmt_struct=FormatSpecs(width=2, fill="0", kind="d", align="="),
        ordered_specs=["fmt"],
    ),
    regex=r"-?0*\d+",
)

examples.add(
    "fmt_float:fmt=.1f",
    GroupSpecs(
        "fmt_float",
        fmt=".1f",
        fmt_struct=FormatSpecs(precision=1, kind="f"),
        ordered_specs=["fmt"],
    ),
    regex=r"-?\d+\.\d{1}",
)

examples.add(
    "fmt_str:fmt=s",
    GroupSpecs(
        "fmt_str",
        fmt="s",
        fmt_struct=FormatSpecs(),
        ordered_specs=["fmt"],
    ),
    regex=r".*?\ *",
)

## Boolean
examples.add(
    "bool_basic:bool=a:b",
    GroupSpecs(
        "bool_basic",
        bool_elts=("a", "b"),
        ordered_specs=["bool"],
    ),
    regex="a|b",
)

examples.add(
    "bool_empty_false:bool=a:",
    GroupSpecs(
        "bool_empty_false",
        bool_elts=("a", ""),
        ordered_specs=["bool"],
    ),
    regex="a|",
)

examples.add(
    "bool_no_false:bool=a",
    GroupSpecs(
        "bool_no_false",
        bool_elts=("a", ""),
        bool_elts_sep="",
        ordered_specs=["bool"],
    ),
    regex="a|",
)

## Prefix/Suffix
examples.add(
    "prefix_int:fmt=02d:pre=_",
    GroupSpecs(
        "prefix_int",
        fmt="02d",
        fmt_struct=FormatSpecs(width=2, fill="0", kind="d", align="="),
        pre="_",
        ordered_specs=["fmt", "pre"],
    ),
    regex=r"-?0*\d+",
)

examples.add(
    "suffix_str:fmt=s:post=_",
    GroupSpecs(
        "suffix_str",
        fmt="s",
        fmt_struct=FormatSpecs(),
        post="_",
        ordered_specs=["fmt", "post"],
    ),
    regex=r".*?\ *",
)

examples.add(
    "prefix_bool:bool=a:b:pre=_",
    GroupSpecs(
        "prefix_bool",
        bool_elts=("a", "b"),
        pre="_",
        ordered_specs=["bool", "pre"],
    ),
    regex="a|b",
)

examples.add(
    "prefix_rgx:rgx=.*:pre=_",
    GroupSpecs(
        "prefix_rgx",
        rgx=".*",
        pre="_",
        ordered_specs=["rgx", "pre"],
    ),
    regex=".*",
)

examples.add(
    "prefix_opt:rgx=.*:pre=_:opt",
    GroupSpecs(
        "prefix_opt",
        rgx=".*",
        pre="_",
        opt=True,
        ordered_specs=["rgx", "pre", "opt"],
    ),
    regex=".*",
)

## Regex

examples.add(
    "custom_rgx:rgx=.*",
    GroupSpecs(
        "custom_rgx",
        rgx=".*",
        ordered_specs=["rgx"],
    ),
    regex=".*",
)


examples.add(
    "rgx_override:rgx=.*:fmt=02d",
    GroupSpecs(
        "rgx_override",
        rgx=".*",
        fmt="02d",
        fmt_struct=FormatSpecs(width=2, fill="0", kind="d"),
        ordered_specs=["rgx", "fmt"],
    ),
    regex=".*",
)

## Others
examples.add(
    "optional:rgx=.*:opt",
    GroupSpecs(
        "optional",
        rgx=".*",
        opt=True,
        ordered_specs=["rgx", "opt"],
    ),
    regex=".*",
)


@st.composite
def st_time_segments(draw: Drawer) -> list[str]:
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
            exclude_characters=set("%()\\"),
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
