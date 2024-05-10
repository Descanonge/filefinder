
.. currentmodule:: filefinder

FileFinder documentation
==========================

FileFinder allows to specify the structure of filenames using a simple syntax.
Parts of the file structure varying from file to file are indicated within named
groups, either with format strings or regular expressions (with some pre-defined
values for some names). Once setup, it can:

- Find corresponding files in a directory (and sub-directories)
- Parse values from the filenames
- Select only filenames with specific values
- Generate filenames

The following example will find all files with the structure ``Data/param_[parameter]/[year]/Temperature_[date].nc``::

    finder = Finder('/.../Data', 'param_%(parameter:fmt=.1f)/%(Y)/Temperature_%(Y)%(m)%(d).nc')
    files = finder.get_files()

We can also select only some files, for instance only in january::

    finder.fix_group('m', 1)
    files = finder.get_files()

We can retrieve values from found files::

    filename, matches = finder.files[0]
    parameter = matches["parameter"]
    # the date as a datetime object
    date = filefinder.library.get_date(matches)

And we can generate a filename with a set of parameters::

    finder.make_filename(parameter=0.5, Y=2000, m=1, d=1)
    # Specifying the month is optional since we already fixed it to 1.


Installation
------------

:Requirements: Python >= 3.10

FileFinder can be installed directly from pip::

  pip install filefinder

or from source with::

  git clone https://github.com/Descanonge/filefinder.git
  cd filefinder
  pip install -e .

or

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
