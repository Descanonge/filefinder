
.. currentmodule:: filefinder.finder

Retrieve information
--------------------

As some metadata might only be found in the filenames, FileFinder offer the
possibility to retrieve it easily using matches.

The :attr:`Finder.files` attribute stores files as a list of tuples
containing a filename and its corresponding matches.
One can also get matches from any filename with the
:func:`Finder.get_matches` function.
In both cases, matches are stored as a
:class:`Matches<filefinder.matcher.Matches>` object, containing a list of
:class:`Match<filefinder.matcher.Match>` objects. Each match retain its
position in the filename string (relative to the root), the matched characters,
and if available its parsed value.

A specific match can be obtained using :func:`Matches.get_matches()
<filefinder.matcher.Matches.get_matches>` and either:

  - the index of the matcher in the pre-regex (starting at 0)
  - a string specifying the name of the matcher, or its group and name (with the
    syntax 'group:name'). If multiple matches correspond to the string, a list
    of matches is returned.

.. note ::
    :func:`Matches.__getitem__<filefinder.matcher.Matches.__getitem__>` wraps
    around this method::

        filename, matches = finder.files[0]
        year = matches.get_matches('Y').get_match()
        # or
        year = matches['Y'].get_match()


The package supply the function :func:`library.get_date
<filefinder.library.get_date>` to retrieve a datetime object from those
matches::

  from filefinder.library import get_date
  matches = finder.get_matches(filename)
  date = get_date(matches)


Combine with Xarray
===================

Retrieving information can be used when opening multiple files with
`xarray.open_mfdataset()
<http://xarray.pydata.org/en/stable/generated/xarray.open_mfdataset.html>`__.

:func:`Finder.get_func_process_filename` will turn a function into a
suitable callable for the `preprocess` argument of `xarray.open_mfdataset`.
The function should take an `xarray.Dataset`, a filename, a
:class:`Finder`, and eventual additional arguments as input, and return
an `xarray.Dataset`.
This allows to use the finder and the dataset filename in the pre-processing.
This following example show how to add a time dimension using the filename to
find the timestamp::

  def preprocess(ds, filename, finder):
    matches = finder.get_matches(filename)
    date = library.get_date(matches)

    ds = ds.assign_coords(time=pandas.to_datetime([value]))
    return ds

  ds = xr.open_mfdataset(finder.get_files(),
                         preprocess=f.get_func_process_filename(preprocess))


.. note::

   The filename path sent to the function is automatically made relative to
   the finder root directory, so that it can be used directly with
   :func:`Finder.get_matches`.
