
.. currentmodule:: filefinder

Usage
-----

.. _create-finder:

Create the Finder object
========================

The main entry point of this package is the :class:`.Finder` class.
It takes in a pattern specifying the filename structure to scan for.
The parts that vary from file to file are indicated in the pattern by
parentheses, preceded by a percent sign. Within the parentheses are
specifications for a :class:`~.Group`, that will handle creating
the regular expression to find files and formatting values appropriately.

For instance, to find files contained in the ``/data`` directory and that follow
the structure ``param_[parameter]/[year]/variable_[year]-[month]-[day].nc``::

    finder = Finder(
        "param_%(param:fmt=.1f)/%(Y)/variable_%(Y)-%(m)-%(d).nc",
        root="/data"
    )

.. important::

    Details on how to write the pattern are available at: :doc:`pattern`.

Behind the scenes, the Finder object will transform the pattern into a regular
expression for filenames to match against.

.. _cache:

Cache
+++++

Whenever the :class:`.Finder` scans for files, it will cache the results (see
:ref:`retrieve-files` for how to scan files and access the results).
Changing some parameters may clear the cache:

* changing the value of properties :attr:`~.Finder.scan_everything`,
  :attr:`~.Finder.use_regex`, :attr:`~.Finder.follow_symlinks` will clear the
  cache
* changing the value of :attr:`~.Finder.pattern` or
  :attr:`~.Finder.group_delimiters` will clear the cache, re-create group
  objects, and remove all filters.
* removing filters (via :meth:`~.Finder.clear_filters` or
  :meth:`~.Finder.remove_group_filters`) will clear the cache. Note that adding
  a filter will only remove files from the cache that do not pass that new
  filter.

.. _dates:

Handling dates
++++++++++++++

When working with dates, it is necessary to deal with multiple individual
elements: year, month, day, etc. The package tries to make this easier by
allowing to refer to multiple elements as a single pseudo-group.

Group names that have the form ``<date name>__<date element>`` (with a double
underscore) will be considered date elements (if omitted, date name defaults to
'date', see :ref:`name` for details). All groups with the same date name can be
managed as a single pseudo-group.

Some methods (:meth:`.FileMatch.get_value` and :meth:`.Finder.add_group_filter`)
accept a ``default_date`` argument that specifies the default elements to use
when constructing datetime objects. For instance, if the filename does not
specify the year, we can use 2000 as a default::

    finder = Finder("%(m)-%(d).txt")
    filematch.get_value("date", default_date={"year": 2000})

The default date can be a datetime object, or a mapping containing any elements
among: year, month, day, hour, minute, second. They will replace the default of
1970-01-01 00:00:00.

Restrict values
===============

The filenames to keep when scanning can be restricted using two main ways:
fixing groups to specific values, and/or run arbitrary filters on those
filenames.

.. _fixing:

Fixing
++++++

Each group can be fixed to one value or to a set of possible values. This will
adapt the regular expression used and thus restrict the filenames kept when
scanning.

.. note::

   When :ref:`creating filenames<create-filenames>`, if a group already
   has a fixed value it will be used by default.

Fixing groups is done with the :meth:`.Finder.fix` method. Groups can be
selected either by their index in the filename pattern (starting from 0), or by
their name. If using a name, groups with the same name can be fixed to the same
value all at once.

The given value can be:

* a **number**: will be formatted to a string according to the group
  specification. When scanning files, the string will be properly escaped for
  use in a regular expression.
* a **boolean**: if the group has two options (specified with the
  :ref:`bool<bool>` keyword), one of the options is selected and used as a
  string.
* a :mod:`datetime` object when fixing a date pseudo-group. Each group will
  be fixed to the appropriate date element (year, month, ...).
* **None** if the group is marked as :ref:`optional<opt>`: it will then not
  appear in the filename.
* a **string**: the value is directly interpreted as a regular expression and
  used as-is when scanning files or creating filenames, without further escaping
  or formatting.
* a **list** of any of the above: each element will be formatted to a string if
  not already. When scanning files, all elements are considered by joining them
  with *OR* (``(value1|value2|...)``), and when creating files only the
  **first** element of the list is used.

So with the same example as previously::

  >>> finder.fix(param=3.0)
  will be formatted as "3\.0"
  >>> finder.fix(param="[a-z]+")
  will be kept as is

We could keep only the files corresponding to january::

  finder.fix(m=1)

We could also select specific days using a list::

  finder.fix(d=[1, 3, 5, 7])

When fixing a date pseudo-group to a :mod:`datetime` object, all individual
groups will be fixed with the corresponding element::

    finder = Finder("%(start:Y)-%(start:m)-%(start:d).txt")
    finder.fix(start=datetime(2000, 1, 1))
    # is equivalent to
    finder.fix(start__Y=2000, start__m=1, start__d=1)

    finder = Finder("%(Y)-%(m)-%(d).txt")
    finder.fix(date=datetime(2000, 1, 1))
    # is equivalent to
    finder.fix(Y=2000, m=1, d=1)

.. important::

   Fixing to a list of dates is not equivalent to selecting those exact dates
   because each element is fixed independently of the other.
   For instance, fixing to ``[date(2000, 1, 10), date(2000, 2, 15)]`` will
   select four dates: 2000-01-10, 2000-01-15, 2000-02-10, 2000-02-15.

   To select exactly multiple dates, use a filter::

    finder.add_group_filter("date", lambda d: d in dates)


.. note::

   Fixed values can be changed/overwritten at any time, or unfixed using the
   :meth:`.Finder.unfix` method.


.. _filtering:

Filtering
+++++++++

Using regular expressions makes for a very efficient way to find files that
follow a specific pattern. However, they cannot deal with advanced logic. Thus,
**after** being "validated" by the regular expression, a file can be subjected
to any number of filters. They are two kinds of filters available: **basic**
filters and **group** filters.

A basic filter is a function has the following signature:

.. py:function:: basic_filter(finder, filematch, **kwargs)
    :no-index:

    :param Finder finder: The finder object.
    :param FileMatch filematch: The matches associated to this filename. See
        :ref:`retrieve-information` for details.
    :param ~typing.Any kwargs: Additional keywords passed to the filter.

    :returns: True if the file is to be kept, False otherwise.


Any number of filters can be added using :meth:`.Finder.add_filter`. They will
be applied to each file, in the order they were added. If any filter discards
the file (*ie* it returns False), the file will not be kept (and the next
filters won't run).

.. important::

   Adding a new filter will filter the files already scanned, and removing
   filters will clear the :ref:`cache`.

.. note::

   The same filter can be applied multiple times with different keyword
   arguments::

     finder.add_filter(some_filter, value=1.)
     finder.add_filter(some_filter, value=3.5)

Very often, it is enough to have a filter operate on just the value from a
single group. To that end, one can create a **group** filter by using
:meth:`.Finder.add_group_filter`. This requires a function which acts on a
single value.

For instance, let's say we only need days that are even::

    finder.add_group_filter("d", lambda d: d % 2 == 0)

or where some parameters starts with a specific value::

    finder.add_group_filter("string_param", lambda s: s.startswith("a_"))

When adding a filter for a date pseudo-group, the filter function will receive a
datetime object constructed from the relevant matches in the filename::

    finder.add_group_filter("date", lambda d: d > datetime(2018, 6, 15))

Multiple groups can be tied to a same filter, for instance if there are multiple
groups with the same name. The function will successively run for all the values
parsed from these groups.

Group filters can be removed with :meth:`.Finder.remove_group_filters`.

.. note::

   If the parsing of a group fails, its filters will be ignored unless
   *pass_unparsed=True* is passed to *add_group_filter*, in which case the
   matched string will be passed to the filter.

.. _find-files:

Find files
==========

.. _retrieve-files:

Retrieve files
++++++++++++++

Found files can be accessed with:

* :attr:`.Finder.files`: a list of absolute filenames as :mod:`pathlib` Paths
  objects.
* :attr:`.Finder.matches`: a list of :class:`.FileMatch` objects each containing
  a filename and group values parsed from it.
* :attr:`.Finder.get_files()` which provides some additional options.

All three will automatically scan the disk for files and cache the results for
later access. Files can be scanned manually with :meth:`.Finder.find_files`. The
files are stored in alphabetical order.

:meth:`~.Finder.get_files` can return paths relative to the root directory by
passing *relative=True*. It can also return filenames in nested lists. To that
end, one must provide the ``nested`` argument with a list that specifies the
order in which groups must be nested. Each element of the list gives:

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
        "/data/param_0.0/2012-01-02.nc",
        ...
      ],
      [  # Y = 2013
        "/data/param_0.0/2013-01-01.nc",
        "/data/param_0.0/2013-01-02.nc",
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

   In the example above, it would be equivalent to use ``nested=["param",
   "date"]``, see :ref:`dates`.

.. note::

      This is aimed to work with `xarray.open_mfdataset <https://docs.xarray.dev/en/stable/generated/xarray.open_mfdataset.html#xarray.open_mfdataset>`__,
      which will merge files in a specific order when supplied a nested list of
      files.

.. _retrieve-information:

Retrieve information
++++++++++++++++++++

As some metadata might only be found in the filenames, FileFinder offer the
possibility to retrieve it easily. Information about a scanned file is stored in
a :class:`.FileMatch` object. It contains the filename, root directory, and
match for each group of the pattern.

The property :attr:`.Finder.matches` contains a list of FileMatch objects
corresponding to the scanned files. One can also get a FileMatch for any
filename by calling :meth:`.Finder.find_matches`.

Accessing the FileMatch with a group index or name will return a **parsed**
value::

  >>> filematch = finder.matches[0]
  >>> filematch["param"]
  0.0  # a float, parsed from the filename

This method is fine for most cases, but for some more complex patterns it is
possible to encounter some issues:

* When using a group name, the first group in the pattern with that name is
  taken. A warning is issued if there are multiple groups of that name with
  differing values.
* The parsing of a value from the filename can fail for various reasons, in that
  case an error will be raised.

For more flexibility :meth:`.FileMatch.get_values` will return a list of values
corresponding to the selected group(s). :meth:`.FileMatch.get_value` will return
the first element of that list, raise if the list is empty or warn if the values
are not all equal. Both function can be given the argument ``parse`` to choose
whether to use the parsed value or solely the string that matched. Note that
FileMatch will only parse the value when requested, not at construction.

.. note::

   ``matches[key]`` is a thin wrapper around
   ``matches.get_value(key, parse=True)``.

Using the name of a date pseudo-group will return a datetime object constructed
from relevant matches::

    >>> finder = Finder(
        "%(start:Y)%(start:m)%(start:d)_%(end:Y)%(end:m)%(end:d).txt"
    )
    >>> filematch = finder.find_matches("20120101_20120131.txt")
    >>> filematch["start"]
    datetime.datetime(2012, 1, 1, 0, 0)
    >>> filematch["end"]
    datetime.datetime(2012, 1, 31, 0, 0)

:meth:`~.FileMatch.get_values` and :meth:`~.FileMatch.get_value` can be given a
*default_date* argument to specify the values of missing date elements: see the
methods documentation and :ref:`dates` for details.

.. _directories-in-pattern:

Directories in pattern
++++++++++++++++++++++

If the pattern contains directory separators the :class:`~.finder.Finder` will
explore sub-directories to find the files.

.. important::

   In the pattern, a directory separator should always be indicated with the
   forward slash ``/``, even on Windows where a backslash would normally be
   used. It will be replaced by the correct character when necessary.

   We do this because the backslash has special meanings in regular expressions,
   and it is difficult to disambiguate the two.

The scanning process is as follows. The Finder first generates a regular
expression based on the pattern and the fixed values. This expression is meant
to match paths relative to the root directory and have a capturing group for
each pattern group.
It then explores all sub-directories to find matching files using one of
two methods.

1. By default, the regular expression is split at each path separator
   occurrence, so that we can eliminate folders that do not match the pattern
   and avoid exploring irrelevant sub-directories. We only scan files when
   arriving at the correct depth.
   However, it cannot deal with some patterns in which a group contains a path
   separator.
2. For those more complicated patterns, by setting the parameter
   :attr:`.Finder.scan_everything` to true, we will explore all sub-directories
   up to a depth of :attr:`.Finder.MAX_SCAN_DEPTH`.

The second method can be more costly for some directory structures ---with many
siblings folders for instance--- but can deal with more exotic patterns. A
likely example could be that of an optional directory::

  >>> "basedir/%(subdir:bool=subdir_name/:)rest_of_pattern"
  basedir/rest_of_pattern
  basedir/subdir_name/rest_of_pattern

In both cases, when a file is found, the whole regular expression is applied and
if it is successful the filters are applied next.

.. _create-filenames:

Create filenames
================

Using the information contained in the filename pattern we can also generate
arbitrary filenames. This is done with :meth:`.Finder.make_filename`. Any group
that does not already have its value :ref:`fixed<fixing>` must have a value
supplied as argument, excepted for :ref:`optional<opt>` groups.

So for pattern ``param_%(param:fmt=.1f)/%(Y)-%(m)-%(d)%(id:fmt=d:pre=_:opt).txt``::

  >>> finder.make_filename(param=1.5, Y=2012, m=1, d=5, id=0)
  "/data/param_1.5/2012-01-05_0.txt"

Optional groups can be left empty::

  >>> finder.make_filename(param=1.5, Y=2012, m=1, d=5)
  "/data/param_1.5/2012-01-05.txt"

As always, we can use an equivalent datetime object::

  finder.make_filename(param=1.5, date=date(2012, 1, 5))

If a group is fixed, we do not need to supply a value. It can be overridden
though without affecting it::

  >>> finder.fix(param=2., Y=2014)
  >>> finder.make_filename(m=5, d=1)
  "/data/param_2.0/2014-05-01.txt"
  >>> finder.make_filename(Y=2015, m=6, d=1)
  "/data/param_2.0/2015-06-01.txt"  # Y is still fixed to 2014

As for fixing, a value will be appropriately formatted but a string will be left
untouched (note the prefix is not added when using a string)::

  >>> finder.make_filename(param="this-feels-wrong", m=6, d=1, id="_a")
  "/data/param_this-feels-wrong/2014-06-01_a.txt"
