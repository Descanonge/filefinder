
.. currentmodule:: filefinder.finder

Quickstart
----------

Let's demonstrate the main features of FileFinder using a simple example.
Detailed information about some steps will be provided in separate pages.

We are going to deal with a dataset with multiple files all located in the
directory ``/data/``. They are organized by sub-directories corresponding
to different parameter values, then in yearly sub-directories::

  /data/param_[parameter]/[year]/variable_[date].nc
  /data/param_0.0/2012/variable_2012-01-01.nc
  /data/param_0.0/2012/variable_2012-01-02.nc
  ...
  /data/param_1.5/2012/variable_2012-01-01.nc
  ...


Creating the Finder object
==========================

To manage this, we are going to use the main entry point of this package: the
:class:`~finder.Finder` class. Its main arguments are the root directory
containing the files, and a pattern specifying the filename structure.
The pattern can later be turned into a proper regular expression which allow us
to find the existing files on disk.

::

    finder = Finder(
        "/data/",
        "param_%(param:fmt=.1f)/%(Y)/variable_%(Y)-%(m)-%(d).nc"
    )

The parts that vary from file to file are indicated in the pattern by a group
within parentheses, preceded by a percent sign. Details on the different ways to
specify a varying group are available there: :doc:`pattern`.

Here quickly, for date related parts, we only need to indicate the name:
filefinder has them as :ref:`default<name>`. For the parameter, we indicate a
:ref:`string format<fmt>` for a float.


.. _finding-files:

Finding files
=============

stuff about walking the root directory.
obtaining files.

The finder can then recursively walk the root directory and its sub-folders.
Only the sub-folders matching the regular expression will be looked into.

.. note::

    Sub-folders can simply be indicated in the pattern with the standard OS
    separator character '/' or '\'.


Files can be retrieved with the :func:`Finder.get_files` function, or
the :attr:`Finder.files` attribute. Both will scan the directory for files
if it has not been done yet.
The 'files' attribute also stores the matches. See :doc:`/retrieve_values`
for details on how matches are stored.

:func:`Finder.get_files` can also return nested lists of filenames. This is
aimed to work with `xarray.open_mfdataset
<https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset>`__,
which will merge files in a specific order when supplied a nested list of files.

To this end, one must specify group names to the `nested` argument of the same
function. The rightmost group will correspond to the innermost level.

An :ref:`example<nested-files>` is available..


Fix groups
==========

The package allows to dynamically change the regular expression easily. This is
done by replacing groups in the regular expression by a given string, using
the :func:`Finder.fix_group` and :func:`Finder.fix_groups` methods.

Groups to replace can be selected either by their index in the filename pattern
(starting from 0), or by their name. If using a group name , multiple groups
can be fixed to the same value at once.

If the corresponding group·s have a format specified, and the given value
is not already a string, it will be formatted.
If using a list of values, the strings (given or formatted) will be joined by
a regex *OR* (``(value1|value2|...)``).

If a string is given, special characters will **not** be escaped.
This allows to specify regular expressions.
On the contrary, for a formatted value special characters will be escaped::

  finder.fix_group('foo', '[a-z]+')  # will be kept as is
  finder.fix_group('bar', 3.)  # will be formatted as '3\.0'

For a more practical example, when using the following pattern::

  '%(time:m)/SST_%(time:Y)%(time:m)%(time:d).nc'

we can keep only the files corresponding to january using any of::

  finder.fix_group(0, 1)
  finder.fix_group('m', 1)

We could also select specific days using a list::

  finder.fix_group('d', [1, 3, 5, 7])
