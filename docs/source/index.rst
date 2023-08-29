
.. currentmodule:: filefinder

FileFinder documentation
==========================

FileFinder allows to specify the structure of filenames with a simple syntax.
Parts of the file structure varying from file to file can be indicated with format strings
or regular expressions, with some of those pre-defined (mainly for dates).
Once setup, it can:

- Find corresponding files in a directory
- Parse information from the filenames
- Select only filenames with specific values
- Generate filenames

The following example will find all files with the structure ``Data/[month]/Temperature_[depth]_[date].nc``::

    finder = Finder('/.../Data', '%(m)/Temperature_%(depth:fmt=d)_%(Y)%(m)%(d).nc')
    files = finder.get_files()

We can also select only some files, for instance the first day of each month::

    finder.fix_group('d', 1)
    files = finder.get_files()

We can retrieve values from found files::

    filename, matches = finder.files[0]
    depth = matches['depth'].get_match()
    date = filefinder.library.get_date(matches)

And we can generate a filename with a set of parameters::

    finder.get_filename(depth=100, Y=2000, m=1, d=1)
    # Specifying the day is optional since we already fixed it to 1.


Contents
--------

.. toctree::
   :maxdepth: 2

   find_files
   retrieve_values
   fix_groups
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
