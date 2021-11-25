
# FileFinder

> Find files using a simple syntax.

<div align="left">

[![PyPI](https://img.shields.io/pypi/v/filefinder)](https://pypi.org/project/filefinder)
[![GitHub release](https://img.shields.io/github/v/release/Descanonge/filefinder)](https://github.com/Descanonge/filefinder/releases)

</div>

FileFinder allows to specify the structure of filenames with a simple syntax.
Parts of the file structure varying from file to file can be indicated with format strings
or regular expressions, or with pre-defined defaults (mainly for dates).
Once setup, it can:

- Find corresponding files in a directory
- Parse information from the filenames
- Select only filenames with specific values
- Generate filenames

The package also interface easily with `xarray.open_mfdataset`.

# Quick examples

The following example will find all files with the structure ``Data/[month]/Temperature_[depth]_[date].nc``:
``` python
finder = Finder('/.../Data', '%(m)/Temperature_%(depth:fmt=d)_%(Y)%(m)%(d).nc')
files = finder.get_files()
```

We can also select only some files, for instance the first day of each month:
``` python
finder.fix_matcher('d', 1)
files = finder.get_files()
```

We can retrieve values from found files:
``` python
filename, matches = finder.files[0]
depth = matches['depth'].get_match()
date = filefinder.library.get_date(matches)
```

And we can generate a filename with a set of parameters:
``` python
finder.get_filename(depth=100, Y=2000, m=1, d=1)
# Specifying the day is optional since we already fixed it to 1.
```


## Requirements

Python >= 3.7.

## Installation

From pip:
``` sh
pip install filefinder
```

From source:
``` sh
git clone https://github.com/Descanonge/filefinder.git
cd filefinder
pip install -e .
```

## Documentation

Documentation is available at [filefinder.readthedocs.io](https://filefinder.readthedocs.io).
