
# v1.0.0

Major overhaul, mainly streamlining.
- Renamed 'matchers' to 'groups' to be consistent with regex tools.
- Removed the 'group' spec (no more 'group:name' stuff, there is only a name now).
- Removed caching of regex and its resulting complications.
- Moved fixing to the Group object, not the Finder.
- Renamed `Finder.get_matches` to `find_matches`.
- Renamed `Finder.get_filename` to `make_filename`.
- `make_filename` now re-use the value-fixing done by groups, instead of having its own (nearly duplicate) logic.
- Make some Finder attribute public.
- Better API to retrieve values with `Matches.get_values` and `Matches.get_value`.
  They now take into account the 'discard' option.
- `Matches.__getitem__` now wraps `Match.get_value`. I think this is the most useful function.

## v0.5.0

- [2022-08-24] Make parts of the API private
- [2022-08-24] Do not throw if no files are found in the filetree.

### v0.4.2

- [2022-01-13] Add methods to get absolute/relative paths

### v0.4.1

- [2021-11-25] Simple eE exponent regex and various reformating.
- [2021-06-15] Better error message when no files are found.

## v0.4.0

- [2021-05-19] Add optional flag in matcher. 
- [2021-05-19] Fix 0 alignment in regex creation from format.
- [2021-05-19] Add tests for Finder class.

### v0.3.1

- [2021-03-26] Fix get_date parsing of F, x and X elements. Better matchers priority.

## v0.3.0

Major overhaul.
- Renamed package to filefinder.
- Slight changes in custom regex syntax. Will break previous pre-regex.
- Can specify matcher with a format string.
- Custom classes containing matches results.
- Only search subdirectories matching the regex.
- Log messages to debug regex.
- Fix matchers with value or string.
- Unfix matchers.
- New default regex elements.


### v0.2.1

- [2021-02-04] Fix multiple matchers at once.

## v0.2.0

- [2021-01-28] Add possibility to retrieve files in a nested list.
- [2021-01-28] Fix warning on missing matchers in `get_date`.

### v0.1.1

- [2021-01-20] Fix fixing matcher by index.

## v0.1.0


