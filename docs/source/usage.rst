
.. currentmodule:: filefinder.finder

Usage
-----

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


.. _create-finder:

Create the Finder object
========================

To manage this, we are going to use the main entry point of this package: the
:class:`Finder` class. Its main arguments are the root directory
containing the files, and a pattern specifying the filename structure.
The pattern can later be turned into a proper regular expression which allow us
to find the existing files on disk.

::

    finder = Finder(
        "/data/",
        "param_%(param:fmt=.1f)/%(Y)/variable_%(Y)-%(m)-%(d).nc"
    )

The parts that vary from file to file are indicated in the pattern by a group
within parentheses, preceded by a percent sign.

.. important::

    Details on the different ways to specify a varying group are available
    there: :doc:`pattern`.

Here quickly, for date related parts, we only need to indicate the name:
filefinder has them as :ref:`default<name>`. For the parameter, we indicate a
:ref:`string format<fmt>` for a float.

.. _fix-groups:

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

.. _find-files:

Find files
==========

.. _retrieve-files:

Retrieve files
++++++++++++++

Files can be retrieved with the :func:`Finder.get_files` method, or the
:attr:`Finder.files` attribute. Both will automatically scan the directory for
matching files and cache the results for future accesses. The files that are
found are also automatically stored in alphabetical order.

.. note::

    The cache is appropriately voided when using some methods, like for fixing
    groups. For that reason, avoid setting attributes directly and use set
    methods.

what returns get_files.
:func:`Finder.get_files` can also return nested lists of filenames. This is
aimed to work with `xarray.open_mfdataset
<https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset>`__,
which will merge files in a specific order when supplied a nested list of files.

To this end, one must specify group names to the `nested` argument of the same
function. The rightmost group will correspond to the innermost level.

An :ref:`example<nested-files>` is available..

what is stored in files.

Scanning process
++++++++++++++++

At its creation, the :class:`Finder` has all the information it needs to find
the files on disk that correspond to the given pattern under the given root
directory. The scanning process is launched automatically when using
:meth:`Finder.get_files` or :attr:`Finder.files`, but can also be launched
manually using :meth:`Finder.find_files`.

The scanning process is as follows. It first generates a regular expression
based on the pattern and the fixed values. This expression is meant to match
paths relative to the root directory and have a capturing group for each pattern
group.

The Finder then explore all sub-directories to find matching files using one of
two methods.

1. By default, the regular expression is split at each path separator
   occurrence, so that we can eliminate folders that do not match the pattern.
   However, it cannot deal with some patterns in which a group contains a path
   separator.
2. For those more complicated patterns, by setting the attribute/parameter
   :attr:`Finder.scan_everything` to true, we will explore all sub-directories
   up to a depth of :attr:`Finder.max_scan_depth`.

The second method can be more costly for some directory structures ---with many
siblings folders for instance--- but can deal with more exotic patterns. A
likely example could be that of an optional directory::

  >>> "basedir/%(subdir:bool=subdir_name/:)rest_of_pattern"
  basedir/rest_of_pattern
  basedir/subdir_name/rest_of_pattern


Create filenames
================

quick demo
explanation about already fixed values.


.. _retrieve-information:

Retrieve information
====================

As some metadata might only be found in the filenames, FileFinder offer the
possibility to retrieve it easily using 'matches'.

The :attr:`Finder.files` attribute stores a list of tuples each containing a
filename and an object.... its corresponding matches. One can also scan any
filename for matches with the :func:`Finder.find_matches` function. In both
cases, matches are stored as a :class:`~.matches.Matches` object, which contain
a list of :class:`~.matches.Match` objects. Each match retain its position in
the filename string (starting at the end of the root directory), the matched
characters, and if available its parsed value.

.. currentmodule:: filefinder.matches

A specific match can be obtained using :func:`Matches.get_matches` and either
the index of the group in the pattern (starting at 0), or a group name.
Because multiple groups can share the same name, a list of all corresponding
:class:`Match` is returned.

.. warning::

    By default, groups with the 'discard' option are not kept.
    This can be overridden with the ``discard=False`` keyword argument.

In most cases, we only care about the value of the group (parsed or not). In
that case we can use :func:`Matches.get_values` or :func:`Matches.get_value`
which directly returned the value (parsed or not, depending on the ``parse``
keyword argument).

:func:`Matches.get_values` always returns a list of values, and
:func:`Matches.get_value` a single value (if multiple groups are selected,
the value from the first one in the filename pattern is returned).

.. note::

   :func:`Matches.__getitem__` wraps around :func:`Matches.get_value`,
   with ``parse=True`` and ``discard=True``.

So, here are a couple of ways to retrieve values from a filename::

  finder = Finder('/data', '%(Y)/SST_%(Y)%(m)%(d).nc')
  file, matches = finder.files[0]

  # Finding the Match


.. currentmodule:: filefinder

The package supply the function :func:`library.get_date` to retrieve a
:class:`~datetime.datetime` object from those matches::

  from filefinder.library import get_date
  matches = finder.get_matches(filename)
  date = get_date(matches)
