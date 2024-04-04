
.. currentmodule:: filefinder.matches

Retrieve information
====================

As some metadata might only be found in the filenames, FileFinder offer the
possibility to retrieve it easily using 'matches'.

The :attr:`Finder.files<filefinder.finder.Finder.files>` attribute stores a list
of tuples each containing a filename and an object.... its corresponding matches.
One can also scan any filename for matches with the
:func:`Finder.find_matches()<filefinder.finder.Finder.find_matches>` function.
In both cases, matches are stored as a
:class:`Matches` object, which contain a list of
:class:`Match` objects. Each match retain its
position in the filename string (starting at the end of the root directory), the
matched characters, and if available its parsed value.

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


The package supply the function :func:`library.get_date` to retrieve a datetime
object from those matches::

  from filefinder.library import get_date
  matches = finder.get_matches(filename)
  date = get_date(matches)
