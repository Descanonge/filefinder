"""Test Matches features.

Basic features on matching filenames.
"""

import pytest
from filefinder.finder import Finder
from hypothesis import given
from util import StPattern, StructPattern


@given(struct=StPattern.pattern())
def test_match_filename_values(struct: StructPattern):
    """Test values in a matched filename are correctly parsed.

    Pattern is generated automatically with appropriate values (and formatted values).
    The reference filename is constructed from the pattern segments and the formatted
    values that were drawn.

    For each group that has a definition allowing to generate a value, we check that
    filefinder has correctly parsed the value back.
    If the group has no discard flag, we also test Matches.__getitem__.
    """
    # reference filename
    filename = struct.filename

    f = Finder("", struct.pattern)
    matches = f.find_matches(filename)

    # Correct number of matches
    assert len(matches) == len(struct.groups)

    for i, (val, val_str) in enumerate(zip(struct.values, struct.values_str)):
        # Unparsable group definition
        if val is not None:
            assert matches.get_value(key=i, parse=True, discard=False) == val
            if not struct.groups[i].discard:
                assert matches[i] == val
            else:
                with pytest.raises(KeyError):
                    _ = matches[i]

        assert matches.get_value(key=i, parse=False, discard=False) == val_str


@given(struct=StPattern.pattern())
def test_make_filename(struct: StructPattern):
    """Test filename creation."""
    f = Finder("/base/", struct.pattern)
    fixes = {i: s for i, s in enumerate(struct.values_str)}
    assert f.make_filename(fixes, relative=True) == struct.filename


@pytest.mark.parametrize("pattern", ["ab%(foo:fmt=d)", "ab%(foo:rgx=.*)"])
def test_wrong_filename(pattern: str):
    """Test obviously wrong filenames that won't match.

    Not sure if there is a way to generate wrong filenames in the most general case.
    """
    f = Finder("", pattern)
    with pytest.raises(ValueError):
        f.find_matches("bawhatever")
