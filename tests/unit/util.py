"""Generation of parameters."""

import itertools
import re
from collections import abc
from dataclasses import dataclass, field

from filefinder.format import Format, FormatError
from hypothesis import strategies as st


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
        return st.one_of(st.none(), st.integers(0, 256))

    @classmethod
    def precision(cls) -> st.SearchStrategy[int | None]:
        return st.one_of(st.none(), st.integers(0, 64))

    @classmethod
    def fill(cls) -> st.SearchStrategy[str]:
        alph = st.characters(
            exclude_categories=["Cc", "Cs"],
            exclude_characters=["{", "}"],
        )
        return st.text(alphabet=alph, min_size=0, max_size=1)

    @staticmethod
    def filter_dangerous(fmt: StructFormat) -> bool:
        """Filter out dangerous format strings."""
        try:
            Format(fmt.fmt)
        except FormatError:
            return False
        return True

    @classmethod
    def format(
        cls, kind: str = "sdfeE", safe: bool = False
    ) -> st.SearchStrategy[StructFormat]:
        """Generate a format."""

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
            strat = strat.filter(cls.filter_dangerous)

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
    fmt: str | None = None
    rgx: str | None = None
    bool_elts: tuple[str, str] | None = None
    opt: bool = False
    discard: bool = False
    ordered_specs: list[str] = field(default_factory=lambda: [])

    def __contains__(self, key: str) -> bool:
        return key in self.ordered_specs

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


class StGroup:
    """Store group related strategies."""

    alphabet = st.characters(exclude_characters=["(", ")", ":", "\n"])

    @classmethod
    def name(cls) -> st.SearchStrategy[str]:
        return st.text(alphabet=cls.alphabet, min_size=1)

    @classmethod
    def rgx(cls) -> st.SearchStrategy[str]:
        return (
            st.text(alphabet=cls.alphabet, min_size=1)
            .filter(lambda s: re.search("%[a-zA-Z]", s) is None)
            .map(lambda s: s.replace("%%", "%"))
        )

    @classmethod
    def fmt(cls) -> st.SearchStrategy[str]:
        return StFormat.format(safe=True).map(lambda s: s.fmt)

    @classmethod
    def bool_elts(cls) -> st.SearchStrategy[tuple[str, str]]:
        @st.composite
        def comp(draw) -> tuple[str, str]:
            a = draw(cls.rgx().filter(lambda s: len(s) > 0))
            b = draw(cls.rgx())
            return a, b

        return comp()

    @classmethod
    def opt(cls) -> st.SearchStrategy[bool]:
        return st.just(True)

    @classmethod
    def discard(cls) -> st.SearchStrategy[bool]:
        return st.just(True)

    @classmethod
    def group(cls) -> st.SearchStrategy[StructGroup]:
        @st.composite
        def comp(draw):
            specs = ["fmt", "rgx", "bool_elts", "opt", "discard"]
            # select the specs to use
            chosen = draw(st.lists(st.sampled_from(specs), unique=True, max_size=5))
            values = {spec: draw(getattr(cls, spec)()) for spec in chosen}
            values["name"] = draw(cls.name())
            return StructGroup(**values, ordered_specs=chosen)

        return comp()
