"""Test Matches features."""

import pytest
from filefinder.finder import Finder
from hypothesis import given
from util import StPattern, StructPattern


@given(struct=StPattern.pattern())
def test_matches(struct: StructPattern):
    f = Finder("", struct.pattern)
    filename = struct.filename
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
    f = Finder("/base/", struct.pattern)
    fixes = {i: s for i, s in enumerate(struct.values_str)}
    assert f.make_filename(fixes, relative=True) == struct.filename


@pytest.mark.parametrize("pattern", ["ab%(foo:fmt=d)", "ab%(foo:rgx=.*)"])
def test_wrong_filename(pattern: str):
    f = Finder("", pattern)
    with pytest.raises(ValueError):
        f.find_matches("bawhatever")
