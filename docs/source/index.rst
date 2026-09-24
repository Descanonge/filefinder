
.. currentmodule:: filefinder

FileFinder documentation
==========================

.. card::

    *Glob on steroids!*

FileFinder allows to specify the structure of filenames using a simple syntax.
Parts of the file structure varying from file to file are indicated within named
groups, similarly to a regular expression. Once setup, it can:

- Find corresponding files in a directory (and sub-directories)
- Parse values from the filenames
- Select only filenames with specific values
- Generate filenames

The following example will find all files with the structure ``Data/depth_[depth]/[year]/Temperature_[date].nc``::

    finder = Finder(
        'depth_%(depth:fmt=.1f)/%(Y)/Temperature_%(Y)%(m)%(d).nc'
        root="/.../Data"
    )
    files = finder.get_files()

We can restrict the values of some parameters, for instance if we only want the
files for January::

    finder.fix(m=1)
    files = finder.get_files()

Or we can apply more complicated filters::

    finder.add_group_filter("m", lambda m: m % 2 == 0)

We can retrieve values parsed from found files::

    filematch = finder.matches[0]
    filematch["depth"]  # a float
    filematch["date"]  # a datetime object

By supplying values for all parameters, we can generate a filename::

    finder.make_filename(depth=0.5, Y=2000, m=1, d=1)
    # Specifying the month is optional since we already fixed it to 1.

Installation
------------

:Requirements: Python >= 3.11

FileFinder can be installed directly from pip::

  pip install filefinder

or from source with::

  git clone https://github.com/Descanonge/filefinder.git
  cd filefinder
  pip install -e .


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
