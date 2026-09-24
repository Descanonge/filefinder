
# FileFinder

> Glob on steroids!

<div align="left">

[![PyPI](https://img.shields.io/pypi/v/filefinder)](https://pypi.org/project/filefinder)
[![GitHub release](https://img.shields.io/github/v/release/Descanonge/filefinder)](https://github.com/Descanonge/filefinder/releases)
[![codecov](https://codecov.io/github/Descanonge/filefinder/branch/master/graph/badge.svg?token=D5OBXX61HM)](https://codecov.io/github/Descanonge/filefinder)
![test status](https://github.com/Descanonge/filefinder/actions/workflows/tests.yml/badge.svg)
[![Documentation Status](https://readthedocs.org/projects/filefinder/badge/?version=latest)](https://filefinder.readthedocs.io/en/latest/?badge=latest)

</div>

FileFinder allows to specify the structure of filenames using a simple syntax.
Parts of the file structure varying from file to file are indicated within named
groups, similarly to a regular expression. Once setup, it can:

- Find corresponding files in a directory (and sub-directories)
- Parse values from the filenames
- Select only filenames with specific values or which pass filter functions
- Generate filenames

## Quick examples

The following example will find all files with the structure ``Data/depth_[depth]/[year]/Temperature_[date].nc``:
``` python
finder = Finder(
    'depth_%(depth:fmt=.1f)/%(Y)/Temperature_%(Y)%(m)%(d).nc',
    root='/.../Data'
)
files = finder.get_files()
```

We can restrict the values of some parameters, for instance if we only
want the files for January::
``` python
finder.fix(m=1)
files = finder.get_files()
```

Or we can apply more complicated filters::
``` python
finder.add_group_filter("m", lambda m: m % 2 == 0)
```

We can retrieve values parsed from found files:
``` python
filematch = finder.matches[0]
filematch["depth"]  # a float
filematch["date"]  # a datetime object
```

By supplying values for all parameters, we can generate a filename:
``` python
finder.make_filename(depth=0.5, Y=2000, m=1, d=1)
# Specifying the month is optional since we already fixed it to 1.
```

## Documentation

Documentation is available at [filefinder.readthedocs.io](https://filefinder.readthedocs.io).

## Requirements

Python >= 3.11

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

