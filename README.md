
# FileFinder

> Find files

<div align="left">

[![PyPI version](https://badge.fury.io/py/filefinder.svg)](https://badge.fury.io/py/filefinder)
[![Release status](https://img.shields.io/github/v/release/Descanonge/filefinder)](https://github.com/Descanonge/filefinder/releases)

</div>

FileFinder allows to specify the structure of filenames and using that, to
find files matching this structure, select only a subset of thoses files
according to parameters values, retrieve parameters values from found filenames,
or to generate a filename according to a set of parameters values.

The structure of the filename is specified with a single string. The parts
of the structure varying from file to file can be indicated with format strings,
or regular expressions, with some of those pre-defined (mainly for dates).

The package also allows to interface easily with `xarray.open_mfdataset`.

# Quick examples

The following example will find all files with the structure ``Data/[month]/Temperature_[depth]_[date].nc``:
``` python
finder = Finder('/.../Data', '%(m)/Temperature_%(depth:fmt=d)_%(Y)%(m)%(d).nc')
print(finder.get_files())
```

We can also only select some files, for instance the first day of each month:
``` python
finder.fix_matcher('d', 1)
print(finder.get_files())
```

We can retrieve values from found files:
``` python
matches = finder.files[0][1]
print(matches)
print(filefinder.library.get_date(matches))
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
