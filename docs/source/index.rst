
.. currentmodule:: filefinder

FileFinder documentation
==========================

FileFinder allows to specify the structure of filenames using a simple syntax.
Parts of the file structure varying from file to file are indicated within named
groups, similarly to a regular expression. Once setup, it can:

- Find corresponding files in a directory (and sub-directories)
- Parse values from the filenames
- Select only filenames with specific values or which pass filter functions
- Generate filenames

The following example will find all files with the structure ``Data/param_[parameter]/[year]/Temperature_[date].nc``::

    finder = Finder('/.../Data', 'param_%(parameter:fmt=.1f)/%(Y)/Temperature_%(Y)%(m)%(d).nc')
    files = finder.get_files()

We can also select only some files, for instance only in january::

    finder.fix_group('m', 1)
    files = finder.get_files()

Or apply more complicated filters::

    finder.fix_by_filters("m", lambda m: m % 2 == 0)

We can retrieve values from found files::

    filename, matches = finder.files[0]
    parameter = matches["parameter"]
    # the date as a datetime object
    date = matches.get_date()

And we can generate a filename with a set of parameters::

    finder.make_filename(parameter=0.5, Y=2000, m=1, d=1)
    # Specifying the month is optional since we already fixed it to 1.

Date as a special citizen: the "date" group name is (by default, but this can be
deactivated) considered special in some operation, like fixing multiple groups
from a datetime object, or having a filter opering on a full date::

    finder.fix_group("date", datetime(2018, 2, 1))
    finder.fix_by_filter("date", lambda d: d > datetime(2018, 2, 1))

Installation
------------

:Requirements: Python >= 3.10

FileFinder can be installed directly from pip::

  pip install filefinder

or from source with::

  git clone https://github.com/Descanonge/filefinder.git
  cd filefinder
  pip install -e .

or::

  pip install -e https://github.com/Descanonge/filefinder.git#egg=filefinder


Contents
--------

.. toctree::
   :maxdepth: 2

   usage
   pattern

.. toctree::
   :maxdepth: 1

   api


Source code: `<https://github.com/Descanonge/filefinder>`__

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
