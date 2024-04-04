
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

The following example will find all files with the structure ``Data/[year]/Temperature_[depth]_[date].nc``::

    finder = Finder('/.../Data', '%(Y)/Temperature_%(depth:fmt=d)_%(Y)%(m)%(d).nc')
    files = finder.get_files()

We can also select only some files, for instance only in january::

    finder.fix_group('m', 1)
    files = finder.get_files()

We can retrieve values from found files::

    filename, matches = finder.files[0]
    depth = matches["depth"]
    # the date as a datetime object
    date = filefinder.library.get_date(matches)

And we can generate a filename with a set of parameters::

    finder.make_filename(depth=100, Y=2000, m=1, d=1)
    # Specifying the month is optional since we already fixed it to 1.

Contents
--------

.. toctree::
   :maxdepth: 2

   quickstart
   pattern
   retrieve_values
   examples

.. toctree::
   :maxdepth: 1

   api


Source code: `<https://github.com/Descanonge/filefinder>`__

Indices and tables
------------------

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
