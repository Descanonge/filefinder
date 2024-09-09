
.. currentmodule:: filefinder.finder

Filtering
=========

When the files are found on disk when scanning with :meth:`Finder.find_files`,
we can select files by fixing groups, but we can also apply filters. These are
user-defined functions that can tell to keep or discard a file.

Each filter is a function (or any callable) that will receive the finder object,
a filename, the associated matches, and should return True if the file is to be
kept or False otherwise. The signature of a filter function should be as follow:

.. py:function:: filter_signature(finder, filename, matches, **kwargs)

    :param Finder finder: The finder object.
    :param str filename: The filename to keep or discard.
    :param Matches matches: The matches associated to this filename.
    :param ~typing.Any kwargs: Additional keywords passed to the filter.

    :returns: True if `filename` is to be kept, False otherwise.
    :rtype: bool


Any number of filters can be added using :meth:`Finder.add_filter`.
They will be applied to each file, in the order they were added. If any
filter discards the file (*ie* it returns False), the file will not be kept (and
the next filters won't run).

.. note::

   The same filter can be applied multiple times with different keyword
   arguments::

     finder.add_filter(some_filter, value=1.)
     finder.add_filter(some_filter, value=3.5)

This can be useful if multiple matches values are needed (see below for dates),
but often we only want add a filter acting on a single group.
:meth:`Finder.fix_by_filter` allows to do that easily. Here the function only
takes the parsed value of a given group.

.. note::

   By giving the argument *pass_unparsed=True* to *fix_by_filter*, if the
   parsing fails, the matched string will still be passed to the filter, instead
   of being ignored.

For instance, let's say we only need days that are even::

    finder.fix_by_filter("d", lambda d: d % 2 == 0)

or only where some parameters starts with a specific value::

    finder.fix_by_filter("param", lambda s: s.startswith("useful_"))

In the background, this creates a "normal" filter, added to
:attr:`Finder.filters` and executed like others. Any number of filters can be
added for a specific group. When unfixing a group, related filters will also be
removed.

.. currentmodule:: filefinder


Examples of filters
-------------------

The package provides two filters. The first one,
:func:`library.filter_by_range`, allows to keep filename which have values
parsed for one of the group that fall within a certain range::

    from filefinder.library import filter_date_range

    f = Finder("/data", "file_%(x:fmt=d).nc")
    # values of 'x' will need to be greater or equal to 5
    f.add_filter(filter_by_range, group="x", min=5)

    # values will need to fall between 5 and 10  boundaries included)
    f.clean_filters()
    f.add_filter(filter_by_range, group="x", min=5, max=10)

This is equivalent to::
    f.fix_by_filter("x", lambda x: 5 <= x <= 10)

:func:`library.filter_date_range`
will only keep files that correspond to a date which falls within a specified
range (start and stop dates are included). It can be applied as such::

    from filefinder.library import filter_date_range

    f = Finder("/data", "my_variable_%(Y)-%(m)-%(d).nc")
    f.add_filter(
        filter_date_range,
        start="2018/06/12",
        stop="2018/07/15"
    )
    f.fix_groups(Y=2018, m=[6, 7])
    files = f.get_files()

Here we specify an arbitrary date range, that could not be replicated only with
fixing groups. We still fix the year and months to help reduce the number of
files to filter.
