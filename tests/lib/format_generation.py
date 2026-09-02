"""Format-related utilities and strategies."""

import math
import sys
from dataclasses import dataclass
from typing import Any

from hypothesis import strategies as st

from filefinder.format import Format, FormatError
from lib import MAX_CODEPOINT, MAX_TEXT_SIZE, Drawer, build_exclude, form


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

    def get_regex(self, *, capture: bool = False) -> str:
        return Format(self.format_string).get_regex(capture=capture)

    def get_value_strategy(
        self, *, for_pattern: bool = False, for_filename: bool = False
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
            if sys.platform in ["win32", "cygwin", "macos"]:
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
        strat = strat.filter(math.isfinite)
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
        cls, *, for_pattern: bool = False, for_filename: bool = False
    ) -> st.SearchStrategy[str]:
        """Strategy for fill characters.

        '{}' characters are excluded to avoid format-calls issues. Other characters are
        excluded using :func:`build_exclude`.
        """
        exclude = build_exclude(set("{}"), for_pattern, for_filename)

        alph = st.characters(
            exclude_categories=["Cc", "Cs"],
            exclude_characters=exclude,
            max_codepoint=MAX_CODEPOINT,
        )
        return st.text(alphabet=alph, min_size=0, max_size=1)

    @classmethod
    def format(
        cls,
        kind: str = "sdfeE",
        *,
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

            return FormatSpecs(
                kind=k,
                fill=fill,
                **{spec: draw(getattr(cls, spec)()) for spec in to_draw},
            )

        strat = comp()

        if safe:
            strat = strat.filter(lambda fmt: fmt.is_valid())

        return strat

    @classmethod
    def value(
        cls,
        st_specs: st.SearchStrategy[FormatSpecs],
        *,
        for_pattern: bool = False,
        for_filename: bool = False,
    ) -> st.SearchStrategy[Any]:
        """Return strategy for value corresponding to a given format-specs strategy."""

        @st.composite
        def strat(draw: Drawer) -> Any:
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
        *,
        safe: bool = True,
        for_pattern: bool = False,
        for_filename: bool = False,
    ) -> tuple[st.SearchStrategy[FormatSpecs], st.SearchStrategy[Any]]:
        """Return a strategy for a format and the corresponding value strategy."""
        specs = st.shared(
            cls.format(
                kind=kind, safe=safe, for_pattern=for_pattern, for_filename=for_filename
            )
        )
        value = cls.value(specs, for_pattern=for_pattern, for_filename=for_filename)
        return specs, value
