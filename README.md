
# FileFinder

> Find files using a simple syntax.

<div align="left">

[![PyPI](https://img.shields.io/pypi/v/filefinder)](https://pypi.org/project/filefinder)
[![GitHub release](https://img.shields.io/github/v/release/Descanonge/filefinder)](https://github.com/Descanonge/filefinder/releases)
[![codecov](https://codecov.io/github/Descanonge/filefinder/branch/master/graph/badge.svg?token=D5OBXX61HM)](https://codecov.io/github/Descanonge/filefinder)
![test status](https://github.com/Descanonge/filefinder/actions/workflows/tests.yml/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/filefinder/badge/?version=latest)](https://filefinder.readthedocs.io/en/latest/?badge=latest)

</div>

FileFinder allows to specify the structure of filenames using a simple syntax.
Parts of the file structure varying from file to file are indicated within named
groups, either with format strings or regular expressions (with some pre-defined
values for some names). Once setup, it can:

- Find corresponding files in a directory (and sub-directories)
- Parse values from the filenames
- Select only filenames with specific values
- Generate filenames

## Quick examples

The following example will find all files with the structure ``Data/param_[parameter]/[year]/Temperature_[date].nc``:
``` python
finder = Finder('/.../Data', 'param_%(parameter:fmt=.1f)/%(Y)/Temperature_%(Y)%(m)%(d).nc')
files = finder.get_files()
```

We can also select only some files, for instance only in january:
``` python
finder.fix_group('m', 1)
files = finder.get_files()
```

We can retrieve values from found files:
``` python
filename, matches = finder.files[0]
parameter = matches["parameter"]
# the date as a datetime object
date = filefinder.library.get_date(matches)
```

And we can generate a filename with a set of parameters:
``` python
finder.make_filename(parameter=0.5, Y=2000, m=1, d=1)
# Specifying the month is optional since we already fixed it to 1.
```

## Requirements

Python >= 3.10

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
or
``` sh
pip install -e https://github.com/Descanonge/filefinder.git#egg=filefinder
```

## Documentation

Documentation is available at [filefinder.readthedocs.io](https://filefinder.readthedocs.io).
