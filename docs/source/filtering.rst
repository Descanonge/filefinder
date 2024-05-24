
.. currentmodule:: filefinder.finder

Filtering
=========

After the files are found on disk in :meth:`Finder.find_files`, filters can be
applied to keep or discard those files.

.. note::

   This has nothing to do with :ref:`fixing groups<fix-groups>`! The files found
   at this point are already restricted by the different fixed groups.

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


.. currentmodule:: filefinder


Examples of filter
------------------

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
