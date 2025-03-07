
.. currentmodule:: filefinder

Usage
-----

.. _create-finder:

Create the Finder object
========================

The main entry point of this package is the :class:`.Finder` class. Its main
arguments are the root directory containing the files, and a pattern specifying
the filename structure. For instance for files contained in the ``/data``
directory that follow the structure
``param_[parameter]/[year]/variable_[Y]-[m]-[d].nc``, with the parameter being a
float with a precision of one decimal::

    finder = Finder(
        "/data",
        "param_%(param:fmt=.1f)/%(Y)/variable_%(Y)-%(m)-%(d).nc"
    )

The parts that vary from file to file are indicated in the pattern by
parentheses, preceded by a percent sign. Within the parentheses are
specifications for a :class:`.group.Group`, that will handle creating
the regular expression to find files and formatting values appropriately.

For date related groups, we only need to indicate the name as filefinder has
some :ref:`default<name>` group names. For the parameter we can simply indicate
a :ref:`string format<fmt>`.

.. important::

    Details on the different ways to specify a group are available at:
    :doc:`pattern`.


Restrict values
===============

The filenames to keep can be restricted using two main ways: directly fixing
groups to specific values, or/and run arbitrary filters on those filenames.

.. _fix-groups:

Fix Groups
++++++++++

Each group can be fixed to one value or to a set of possible values. This will
adapt the regular expression used and thus restrict the filenames when scanning.

.. note::

   Also, when :ref:`creating filenames<create-filenames>`, if a group already
   has a fixed value it will be used by default.

Fixing groups can be done with either the :meth:`.Finder.fix_group` or
:meth:`.Finder.fix_groups` methods.
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

For further examples, we could keep only the files corresponding to january::

  finder.fix_groups("m", 1)

We could also select specific days using a list::

  finder.fix_groups(d=[1, 3, 5, 7])

.. note::

   Fixed values can be changed/overwritten at any time, or unfixed using the
   :meth:`.Finder.unfix_groups` method.

.. warning::

  A group flagged as :ref:`:discard<discard>` will not be fixed by default,
  unless using the keyword argument ``fix_discard`` in
  :meth:`~.Finder.fix_group` and :meth:`~.Finder.fix_groups`.


.. _filtering:

Filtering
+++++++++

Using regular expressions makes for a very efficient way to find files that
follow a specific pattern. However, they cannot deal with advanced logic with
which one might want to select the files. Thus, **after** being "validated" by
the pattern (and its eventual fixed groups) a file can be subjected to any
number of filters. They are three kinds of filters available: **basic** filters,
**group** filters, and **date** filters.

A basic filter is a function has the following signature:

.. py:function:: basic_filter(finder, filename, matches, **kwargs)
    :no-index:

    :param Finder finder: The finder object.
    :param str filename: The filename to keep or discard. Relative to the root
                         directory of the Finder.
    :param Matches matches: The matches associated to this filename.
    :param ~typing.Any kwargs: Additional keywords passed to the filter.

    :returns: True if `filename` is to be kept, False otherwise.


Any number of filters can be added using :meth:`.Finder.add_filter`. They will
be applied to each file, in the order they were added. If any filter discards
the file (*ie* it returns False), the file will not be kept (and the next
filters won't run).

.. important::

   Adding a new filter will filter the files already scanned, and removing
   filters will void the cache.

.. note::

   The same filter can be applied multiple times with different keyword
   arguments::

     finder.add_filter(some_filter, value=1.)
     finder.add_filter(some_filter, value=3.5)

Very often, it can suffice to have a filter operate on the value from a single
group. To that end, one can create a **group** filter by using
:meth:`.Finder.fix_by_filter`. This requires a function which act on a single
value.

For instance, let's say we only need days that are even::

    finder.fix_by_filter("d", lambda d: d % 2 == 0)

or where some parameters starts with a specific value::

    finder.fix_by_filter("param", lambda s: s.startswith("useful_"))

Multiple groups can be tied to a same filter, for instance if there are multiple
groups with the same name. The function will successively run for all the values
parsed from these groups (except those marked as :ref:`to discard<discard>`).

A group can be fixed with any number of filters *as well as* to a value (with
:ref:`fixing<fix-groups>`). When unfixing a group, both the value and the
filters will be removed.

Lastly one can create a **date** filter by giving the group name "date" to
*fix_by_filter*. The filter function will receive a :class:`~datetime.datetime`
object obtained from all relevant matches. These filters differ from group
filters in that individual groups cannot be removed from it, as date filters act
on all matches. The whole date filter has to be removed.

See the next section for more information on the "date" group exception.

.. note::

   If the parsing of a group fails, its filters will be ignored unless
   *pass_unparsed=True* is passed to *fix_by_filter*, in which case the matched
   string will be passed to the filter.

.. note::

   Some filters functions are provided: :func:`.library.filter_by_range` and
   :func:`.library.filter_date_range`. They are kept for compatibility but are
   not as useful since the addition of *fix_by_filter* and "date" as first
   class citizen (see below).


.. _dates:

Special case: dates
+++++++++++++++++++

When working with dates, it is necessary to deal with multiple individual
elements: year, month, day, etc. The package tries to make this easier by
attributing a special meaning to the group key **"date"**. For instance, if
passed to *fix_group*, all the time-related groups will be fixed from a
single :class:`~datetime.datetime` object::

    >>> finder = Finder("", "%(Y)/%(m)/%(var:fmt=s)_%(Y)-%(j).ext")
    >>> finder.fix_group("date", datetime(2018, 2, 1))
    Will fix Y:2018, m:2, and j:32 (dayofyear)

Similarly, when used as a key in :meth:`~.Finder.fix_by_filter`, the filter
will receive a datetime object constructed from the matches in the filename::

    finder = Finder("", "%(Y)/%(m)/%(var:fmt=s)_%(Y)-%(j).ext")
    finder.fix_groups(Y=2018)
    finder.fix_by_filter("date", lambda d: d > datetime(2018, 6, 15))

In this example we only select files corresponding to dates after the 15th of
june. We also selected the year 2018 with a "traditional" value-fix.

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

Files can be retrieved with the :meth:`.Finder.get_files` method, or from the
:attr:`.Finder.files` attribute. Both will automatically scan the directory for
matching files and cache the results for future accesses. The files are stored
in alphabetical order.

.. note::

    The cache is appropriately voided when using some methods, like for fixing
    groups. For that reason, avoid setting attributes directly and use set
    methods.

The method :meth:`~.Finder.get_files` simply returns a sorted list of the
filenames found when scanning. By default the full path is returned, ie the
concatenation of the root directory and the pattern part. It can also return the
filename relative to the root directory (ie only the pattern part).

Instead of a flat list of filenames, :meth:`~.Finder.get_files` can also arrange
them in nested lists. To that end, one must provide the ``nested`` argument with
a list that specify the order in which groups must be nested. Each element of
the list gives:

* a group, by index or name, so that files be grouped together based on the
  value of that group
* multiple groups, by a tuple of indices or names, so files are grouped based
  on the combination of values from those groups.

For instance with the pattern ``param_%(param:fmt=.1f)/%(Y)-%(m)-%(d).nc``, if
we ask to group by values of 'param'::

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
possibility to retrieve it easily. One can find the matching strings and values
of all groups for any filename by calling :meth:`.Finder.get_matches`. It will
return a :class:`~.matches.Matches` object containing all the information.

The files scanned are cached in the :attr:`.Finder.files` attribute as a list of
tuples each containing a filename and a :class:`~.matches.Matches` object.

For most cases, the simplest is to access the Matches object with a group index
or name::

  >>> file, matches = finder.files[0]
  >>> matches["param"]
  0.0  # a float, parsed from the filename

This method is fine for most cases, but for some more complex patterns it is
possible to encounter some issues:

* When using a group name, the first group in the pattern with that name is
  taken. A warning is issued if there are multiple groups of that name with
  differing values.
* Only groups not flagged as ':discard' will be selected. If no group can be
  found, an error will be raised.
* The parsing of a value from the filename can fail for various reasons, in that
  case an error will be raised.

If needed one can use :meth:`.Matches.get_values` which will return a list of
values corresponding to the selected group(s). It has arguments ``keep_discard``
and ``parse`` to choose whether keep discarded groups and whether to use the
parsed value or solely the string that matched. :meth:`.Matches.get_value` will
return the first element of that list, raise if the list is empty or warn if the
values are not all equal.

.. note::

   ``matches[key]`` is a thin wrapper around
   ``matches.get_value(key, parse=True, keep_discard=False)``.

To facilitate working with date, the method :meth:`.Matches.get_date` will
return a :class:`~datetime.datetime` object obtained from the values of the
relevant groups present in the pattern.

Directories in pattern
++++++++++++++++++++++

The pattern can contain directory separators. The :class:`~.finder.Finder` can
explore sub-directories to find the files.

.. important::

   In the pattern, a directory separator should always be indicated with the
   forward slash ``/``, even on Windows where a backslash would be normally be
   used. It will be replaced by the correct character when necessary.

   We do this because the backslash has special meanings in regular expressions,
   and it is difficult to disambiguate the two.

The scanning process is as follows. It first generates a regular expression
based on the pattern and the fixed values. This expression is meant to match
paths relative to the root directory and have a capturing group for each pattern
group.

The Finder then explore all sub-directories to find matching files using one of
two methods.

1. By default, the regular expression is split at each path separator
   occurrence, so that we can eliminate folders that do not match the pattern
   and avoid exploring irrelevant sub-directories. We only scan files when
   arriving at the correct depth.
   However, it cannot deal with some patterns in which a group contains a path
   separator.
2. For those more complicated patterns, by setting the attribute/parameter
   :attr:`.Finder.scan_everything` to true, we will explore all sub-directories
   up to a depth of :attr:`.Finder.max_scan_depth`.

The second method can be more costly for some directory structures ---with many
siblings folders for instance--- but can deal with more exotic patterns. A
likely example could be that of an optional directory::

  >>> "basedir/%(subdir:bool=subdir_name/:)rest_of_pattern"
  basedir/rest_of_pattern
  basedir/subdir_name/rest_of_pattern

In both cases, when a file is found, the whole regular expression is immediately
applied and if it is successful the filters are applied next.

.. _create-filenames:

Create filenames
================

Using the information contained in the filename pattern we can also generate
arbitrary filenames. This is done with :meth:`.Finder.make_filename`. Any group
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
