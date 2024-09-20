
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
That pattern allows to get filenames corresponding to given values, but also
to scan for files matching the pattern on disk.

::

    finder = Finder(
        "/data/",
        "param_%(param:fmt=.1f)/%(Y)/variable_%(Y)-%(m)-%(d).nc"
    )

The parts that vary from file to file are indicated in the pattern by
parentheses, preceded by a percent sign. Within the parentheses are
specifications for a :class:`~filefinder.group.Group`, that will handle creating
the regular expression to find files and formatting values appropriately.

.. important::

    Details on the different ways to specify a varying group are available
    there: :doc:`pattern`.

Here quickly, for date related parts, we only need to indicate the name:
filefinder has them as :ref:`default<name>`. For the parameter, indicating a
:ref:`string format<fmt>` will suffice.


Restrict values
===============

The filenames to keep can be restricted using two main ways: directly fixing
groups to specific values, or run arbitrary filters on said files.

.. _fix-groups:

Fix Groups
++++++++++

Each group can be fixed to one value or a set of possible values. This will
adapt the regular expression used and thus restrict the filenames when scanning.

.. note::

   Also, when :ref:`creating filenames<create-filenames>`, if a group already
   has a fixed value it will be used by default.

Fixing groups can be done with either the :func:`Finder.fix_group` or
:func:`Finder.fix_groups` methods.
Groups can be selected either by their index in the filename pattern (starting
from 0), or by their name. If using a group name, multiple groups can be fixed
to the same value at once.

The given value can be:

* a **number**: will be formatted to a string according to the group
  specification. For scanning files, the string will be properly escaped for
  use in a regular expression.
* a **boolean**: if the group has two options (specified with the
  :ref:`bool<bool>` keyword), one of the options is selected and used as a
  string.
* a **string**: the value is directly interpreted as a regular expression and
  used as-is when scanning files or creating filenames, without further escaping
  or formatting.
* a **list** of any of the above: each element will be formatted to a string if
  not already. When scanning files, all elements are considered by joining them
  with *OR* (``(value1|value2|...)``), and when creating files only the
  **first** element of the list is used.

So for example::

  >>> finder.fix_group("param", "[a-z]+")
  will be kept as is
  >>> finder.fix_group("param", 3.)
  will be formatted as "3\.0"

More practically, we could keep only the files corresponding to january::

  finder.fix_groups("m", 1)

We could also select specific days using a list::

  finder.fix_groups(d=[1, 3, 5, 7])

.. note::

   Fixed values can be changed/overwritten at any time, or unfixed using the
   :meth:`Finder.unfix_groups` method.

.. warning::

  A group flagged as :ref:`:discard<discard>` will not be fixed by default,
  unless using the keyword argument ``fix_discard`` in :meth:`~Finder.fix_group`
  and :meth:`~Finder.fix_groups`.


.. _filtering:

Filtering
+++++++++

Using regular expressions makes for a very efficient way to find files that
follow a specific pattern. However, they cannot deal with advanced logic with
which one might want to select the files. Thus, **after** being "validated" by
the pattern (and its eventual fixed groups) a file can be subjected to any
number of filters. Each filter is a function (or any other callable) with the
following signature:

.. py:function:: filter_signature(finder, filename, matches, **kwargs)

    :param Finder finder: The finder object.
    :param str filename: The filename to keep or discard.
    :param Matches matches: The matches associated to this filename.
    :param ~typing.Any kwargs: Additional keywords passed to the filter.

    :returns: True if `filename` is to be kept, False otherwise.
    :rtype: bool


Any number of filters can be added using :meth:`Finder.add_filter`. They will be
applied to each file, in the order they were added. If any filter discards the
file (*ie* it returns False), the file will not be kept (and the next filters
won't run).

.. note::

   The same filter can be applied multiple times with different keyword
   arguments::

     finder.add_filter(some_filter, value=1.)
     finder.add_filter(some_filter, value=3.5)

.. important::

   Adding a new filter will filter the files already scanned, and clearing the
   filters will void the cache.

.. note:: Implementation detail

    Filters are kept in a dictionary and can be cleared with
    :meth:`.Finder.clear_filters`. If no explicit name is given to *add_filter*
    the name of the callable is used (``func.__name___``) and made unique to
    avoid key clashes.


Very often, it can suffice to have a filter operate on a single group. To that
end, one can use :meth:`Finder.fix_by_filter` where the filter is a function
that act only on the parsed value of a group. If there are multiple groups with
the same name, all values found in the filename will pass through the filter
successively.

For instance, let's say we only need days that are even::

    finder.fix_by_filter("d", lambda d: d % 2 == 0)

or only where some parameters starts with a specific value::

    finder.fix_by_filter("param", lambda s: s.startswith("useful_"))

A group can be fixed with any number of filters, and to a value as well as
described :ref:`above<fix-groups>`. When unfixing a group, its associated
filters will be removed as well.

.. note::

   If the parsing of a group fails, its filters will be ignored unless
   *pass_unparsed=True* is passed to *fix_by_filter*, in which case the matched
   string will be passed to the filter.

.. note::

   Some filters functions are provided: :func:`.library.filter_by_range` and
   :func:`.library.filter_date_range`. They are kept for compatibility but are
   not as useful since the addition of *fix_by_filter* and "date" as first
   class citizen (see below).

.. note:: Implementation details

   Group filters are actually wrapped in a "normal" filter. Their name reflect
   the key they have been fixed to (group index or name), and are made unique.


.. _dates:

Special case: dates
+++++++++++++++++++

When working with dates, it is necessary to deal with different elements. The
package tries to make it easier by attributing a special meaning to the group
key **"date"**. For instance, if passed to *fix_group(s)*, all the time-related
groups will be fixed from a single :class:`~datetime.datetime` object::

    >>> finder = Finder("", "%(Y)/%(m)/%(var:fmt=s)_%(Y)-%(j).ext")
    >>> finder.fix_group("date", datetime(2018, 2, 1))
    Will fix Y:2018, m:2, and j:32 (dayofyear)

Similarly, when used as a key in :meth:`~.Finder.fix_by_filter`, the filter
will receive a datetime object constructed from the matches in the filename::

    finder = Finder("", "%(Y)/%(m)/%(var:fmt=s)_%(Y)-%(j).ext")
    finder.fix_groups(Y=2018)
    finder.fix_by_filter("date", lambda d: d > datetime(2018, 6, 15))

In this example we only select files corresponding to dates after the 15th of
june. We also selected the year 2018 with a "traditionnal" value-fix.

.. note::

   The group names that are impacted are those listed as time-related in the
   :ref:`default group names<name>`, *ie* Y, m, d, H, M, S, j, B, F, x, and X.

.. important::

   This feature is active by default, but can be deactivated by setting the
   attribute :attr:`.Finder.date_is_first_class` to False, either on the Finder
   class or on a specific instance.

.. _find-files:

Find files
==========

.. _retrieve-files:

Retrieve files
++++++++++++++

Files can be retrieved with the :func:`Finder.get_files` method, or from the
:attr:`Finder.files` attribute. Both will automatically scan the directory for
matching files and cache the results for future accesses. The files are stored
in alphabetical order.

.. note::

    The cache is appropriately voided when using some methods, like for fixing
    groups. For that reason, avoid setting attributes directly and use set
    methods.

The method :meth:`~Finder.get_files` simply returns a sorted list of the
filenames found when scanning. By default the full path is returned, ie the
concatenation of the root directory and the pattern part. It can also return the
filename relative to the root directory (ie only the pattern part).

Instead of a flat list of filenames, :func:`~Finder.get_files` can also arrange
them in nested lists. To that end, one must provide the ``nested`` argument with
a list that specify the order in which groups must be nested. Each element of
the list gives:

* a group, by index or name, so that files be grouped together based on the
  value of that group
* multiple groups, by a tuple of indices or names, so files are grouped based
  on the combination of values from those groups.

An example might help to grasp this. Again with the same pattern, we can ask
to group by values of 'param'::

  >>> finder.get_files(nested=["param"])
  [
    [
      "/data/param_0.0/2012-01-01.nc",
      "/data/param_0.0/2012-01-02.nc",
      ...
    ],
    [
      "/data/param_1.5/2012-01-01.nc",
      "/data/param_1.5/2012-01-02.nc",
      ...
    ],
    ...
  ]

We obtain as many lists as different values found for 'param'. Because we
did not specify any other group, the nesting stop there. But we could chose
to *also* group by the year::

  >>> finder.get_files(nested=["param", "Y"])
  [
    [  # param = 0
      [  # Y = 2012
        "/data/param_0.0/2012-01-01.nc",
        ...
      ],
      [  # Y = 2013
        "/data/param_0.0/2013-01-01.nc",
        ...
      ],
      ...
    ],
    [  # param = 1.5
      ...
    ],
    ...
  ]

Or if we wanted to group by date as well we can specify multiple groups for
one nesting level::

  >>> finder.get_files(nested=["param", ("Y", "m", "d")])
  [
    [  # param = 0
      ["/data/param_0.0/2012-01-01.nc"],
      ["/data/param_0.0/2012-01-02.nc"],
      ...
    ],
    [  # param = 1.5
      ["/data/param_1.5/2012-01-01.nc"],
      ["/data/param_1.5/2012-01-02.nc"],
      ...
    ],
    ...
  ]

.. note::

      This is aimed to work with `xarray.open_mfdataset <https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset>`__,
      which will merge files in a specific order when supplied a nested list of
      files.

.. _retrieve-information:

Retrieve information
++++++++++++++++++++

As some metadata might only be found in the filenames, FileFinder offer the
possibility to retrieve it easily. The Finder caches a list of files matching
the pattern, along with information about parts that matched the groups.

The :attr:`Finder.files` attribute stores a list of tuples each containing a
filename and a :class:`~.matches.Matches` object storing that information.

.. note::

    One can also scan any filename for matches with the
    :meth:`Finder.find_matches` function.

.. currentmodule:: filefinder.matches

For most cases, the simplest is to access the Matches object with a group index
or name::

  >>> file, matches = finder.files[0]
  >>> matches["param"]
  0.0  # a float, parsed from the filename

This method has several caveats:

* When using a group name, the first group in the pattern with that name is
  taken, even if there could be more groups with different values (a warning is
  issued if that is the case).
* Only groups not flagged as ':discard' will be selected. If no group can be
  found, an error will be raised.
* The parsing of a value from the filename can fail for a variety of reasons, if
  that is the case, an error will be raised.

To counter those, one can use :meth:`Matches.get_values` which will return
a list of values corresponding to the selected group(s). It has arguments
``keep_discard`` and ``parse`` to choose whether keep discarded groups and
whether to use the parsed value or solely the string that matched.

:meth:`Matches.get_value` will return the first element of that list, raise if
the list is empty, and warn if the values are not all equal.

.. note::

   ``matches[key]`` is a thin wrapper around
   ``matches.get_value(key, parse=True, keep_discard=False)``.

.. currentmodule:: filefinder

As date/time values are scattered among multiple groups, the package supply the
function :func:`library.get_date` to easily retrieve a
:class:`~datetime.datetime` object from matches, accessible directly from the
:meth:`.Matches.get_date`::

  matches = finder.get_matches(filename)
  date = matches.get_date()

.. currentmodule:: filefinder.finder

Directories in pattern
++++++++++++++++++++++

The pattern can contain directory separators. The :class:`Finder` can explore
sub-directories to find the files.

.. important::

   In the pattern, a directory separator should always be indicated with the
   forward slash ``/``, even on Windows where we normally use the backslash. It
   will be replaced by the correct character when necessary.

   We do this because the backslash has special meanings in regular expressions,
   and it is difficult to disambiguate the two.

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


.. _create-filenames:

Create filenames
================

Using the information contained in the filename pattern we can also generate
arbitrary filenames. This is done with :meth:`Finder.make_filename`. Any group
that does not already have its value :ref:`fixed<fix-groups>` must have a value
supplied as argument.
As for fixing, a value will be appropriately formatted but a string will be
left untouched.

So for instance::

  >>> finder.make_filename(param=1.5, Y=2012, m=1, d=5)
  "/data/param_1.5/2012-01-05.nc"

we can also fix some groups::

  >>> finder.fix_groups(param=2., Y=2014)
  >>> finder.make_filename(m=5, d=1)
  "/data/param_2.0/2014-05-01.nc"
  >>> finder.make_filename(m=6, d=1)
  "/data/param_2.0/2014-06-01.nc"

and also supply a string to forgo formatting::

  >>> finder.make_filename(param="this-feels-wrong", m=6, d=1)
  "/data/param_this-feels-wrong/2014-06-01.nc"
