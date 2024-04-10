
Examples
--------

Plain time serie
================

Here is an hypothetical list of files that will be used in some examples below::

    Data
    └── SST
        ├── A_2007001_2007008.nc
        ├── A_2007009_2007016.nc
        ├── A_2007017_2007024.nc
        └── ...

Those are 8 days averages, so there are two varying parts in the filename: the
starting and ending date of average. We will 'discard' the second one, so
that the value that we will be able to fix and retrieve is the starting date::

  from filefinder import Finder, library

  root = 'Data/SST'
  pattern = 'A_%(Y)%(j)_%(Y)%(j:discard).nc'
  finder = Finder(root, pattern)

  files = finder.get_files()

We can retrieve information on the date as well::

  for file, matches in finder.files:
      print(file, 'dayofyear: ', matches.get_value('j'))

  Data/SST/A_2007001_2007008.nc    dayofyear:   1
  Data/SST/A_2007009_2007016.nc    dayofyear:   9
  ...

To be a little bit clearer we could convert this information into a
:class:`~datetime.datetime` object instead. The library provides a function to
do that::

  from filefinder import library
  dates = [(file, library.get_date(matches))
           for file, matches in finder.files]

Now we would like to open all these files using Xarray, however the files lack a
defined 'time' dimensions to concatenate all files. To make it work, we can use
the 'preprocess' argument of :func:`xarray.open_mfdataset`::

  import pandas as pd
  from filefinder import library

  def preprocess(ds, filename, finder):
    matches = finder.find_matches(filename)
    date = library.get_date(matches)
    ds = ds.assign_coords(time=pd.to_datetime([value]))
    return ds

  ds = xr.open_mfdataset(
      files,
      preprocess=library.get_func_process_filename(f, preprocess)
  )


.. _nested-files:

Nested files
============

We now have two variables setup in a similar layout::

     Data
     ├── SSH
     │   ├── SSH_20070101.nc
     │   ├── SSH_20070102.nc
     │   └── ...
     └── SST
         ├── SST_20070101.nc
         ├── SST_20070102.nc
         └── ...

We can scan both variables at the same time and retrieve the files as a
:ref:`nested list<retrieve-files>`.
Group names in the pattern will define what groups will be grouped together::

  pattern = '%(char)/%(char:discard)_%(x).nc'

We can now group the files by variable or time::

  >>> finder.get_files(relative=True, nested=['char'])
  [['SSH_20070101.nc',
    'SSH_20070109.nc',
    ...],
   ['SST_20070101.nc',
    'SST_20070109.nc',
    ...]]

  >>> finder.get_files(relative=True, nested=['x'])
  [['SSH_20070101.nc', 'SST_20070101.nc'],
   ['SSH_20070109.nc', 'SST_20070109.nc'],
   ...]

This works for any number of groups in any order.


Fixing parameters and getting filenames
=======================================

Let's use a pattern with more parameters: an integer, a variable name, and
a floating point parameter::

  pattern = "index_%(index:fmt=d)/var_%(var:fmt=s)_scale_%(scale:fmt=+06.1f).txt"
  finder = Finder('/Data', pattern)

This will automatically produce a regular expression based on the formats::

  >>> print(finder.get_regex())
  index_(-?\d+)/var_(.*?)_scale_(0*[+-]\d+\.\d{1})\.txt

We might want to only capture files for a specific variable::

  finder.fix_group('var', 'SST')
  finder.get_files()

On a second thought, we want files for all variable, but for specific scales::

  finder.unfix_groups('var')
  finder.fix_group('scale', [10., 20., 30.])
  finder.get_files()

Lastly, we can generate a filename following that structure.
We must specify all parameters, except for the scale we fixed earlier (the
first value of the list will be used)::

  >>> finder.make_filename(index=1, var='SSH')
  /Data/index_1/SSH_scale_+010.0.txt
