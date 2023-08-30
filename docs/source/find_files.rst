
.. currentmodule:: filefinder.finder

Finding files
-------------

The main entry point of this package is the :class:`Finder` class. An instance
is created using the root directory containing the files, and a pattern
specifying the filename structure which will be transformed into a proper regex
later.

When asking to find files, the finder will first create a regular-expression
out of the pattern.
It will then recursively find files in the root directory and its subfolders.
Only the subfolders matching (part of) the regex will be looked into.
Subfolders can simply be indicated in the pattern with the standard OS
separator. The finder only keeps files that match the full regex.


Pattern
=======

The pattern specifies the structure of the filenames relative to the root
directory. Parts that vary from file to file are indicated by *groups*,
enclosed by parenthesis and preceded by '%'. It is represented by the
:class:`Group<filefinder.group.Group>` class.

Inside the groups parenthesis can be indicated multiple properties, separated by
colons:

- a **name** (does not need to be unique)
- a **format** string (optional)
- an **option** switch (optional)
- a custom **regex** (optional)
- a **discard** keyword that will ignore that group when retrieving information from a
  filename (optional)

The full syntax is as follows::

    %(name[:fmt=format string][:opt[=A:B]][:rgx=custom regex][:discard])

.. note::

   The groups are uniquely identified by their index in the pattern
   (starting at 0).
   Some functions (see :func:`Finder.find_matches` or :func:`Finder.fix_group`)
   can use a name to find one or more groups.

.. warning::

   Groups are first found in the pattern by looking at matching
   parentheses. The pattern should thus have balanced parentheses or
   unexpected behaviour can occur.


Name
####

The name of the group will dictate the regex and format string used for that
group (unless overriden the 'fmt' and 'rgx' properties).
The :attr:`Group.DEFAULT_GROUPS<filefinder.group.Group.DEFAULT_GROUPS>`
class attribute will make the correspondance between name and regex:

+------+-------------------+-----------+--------+
| Name |                   | Regex     | Format |
+======+===================+===========+========+
| F    | Date (YYYY-MM-DD) | %Y-%m-%d  |      s |
+------+-------------------+-----------+--------+
| x    | Date (YYYYMMDD)   | %Y%m%d    |    08d |
+------+-------------------+-----------+--------+
| X    | Time (HHMMSS)     | %H%M%S    |    06d |
+------+-------------------+-----------+--------+
| Y    | Year (YYYY)       | \\d{4}    |    04d |
+------+-------------------+-----------+--------+
| m    | Month (MM)        | \\d\\d    |    02d |
+------+-------------------+-----------+--------+
| d    | Day of month (DD) | \\d\\d    |    02d |
+------+-------------------+-----------+--------+
| j    | Day of year (DDD) | \\d{3}    |    03d |
+------+-------------------+-----------+--------+
| B    | Month name        | [a-zA-Z]* |      s |
+------+-------------------+-----------+--------+
| H    | Hour 24 (HH)      | \\d\\d    |    02d |
+------+-------------------+-----------+--------+
| M    | Minute (MM)       | \\d\\d    |    02d |
+------+-------------------+-----------+--------+
| S    | Seconds (SS)      | \\d\\d    |    02d |
+------+-------------------+-----------+--------+
| I    | Index             | \\d+      |      d |
+------+-------------------+-----------+--------+
| text | Letters           | \\w       |      s |
+------+-------------------+-----------+--------+
| char | Character         | \\S*      |      s |
+------+-------------------+-----------+--------+

Those are mainly related to datetime. This table *mostly* follows the `strftime
<https://linux.die.net/man/3/strftime>`__ format specifications.
Groups with corresponding names will be used by :func:`library.get_date()<filefinder.library.get_date>` to find the date from
the filename.

A letter preceded by a percent sign '%' in the regex will be recursively
replaced by the corresponding name in the table. This can be used in the
custom regex. This still counts as a single group and its name will not
be changed, only the regex.
So ``%x`` will be replaced by ``%Y%m%d``, in turn replaced by
``\d{4}\d\d\d\d``.
A percentage character in the regex is escaped by another percentage ('%%').


Custom format
#############

All the possible use cases are not covered in the table above. A simple way to
specify a group is by using a format string following the
`Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__.
This will automatically be transformed into a regular expression.

Having a format specified has other benefits: it can be used to convert values
into strings to generate a filename from parameters values (using
:func:`Finder.make_filename`), or vice-versa to parse filenames matches into
parameters values.

It's easy as::

  scale_%(scale:fmt=.1f)

This will find files such as ``scale_15.0`` or ``scale_-5.6``.
Because we know how to transform a value into a string we can fix the group
directly with a value::

  finder.fix_group('scale', 15.)

or we can generate a filename::

  >>> finder.make_filename(scale=2.5)
  'scale_2.5'

In the opposite direction, we can retrieve a value from a filename::

  >>> matches = finder.find_matches('scale_2.5')
  >>> print(matches['scale'].get_match())
  2.5  # a float

If the format is never specified, it defaults to a ``s`` format.

.. warning::

   Only s, d, f, e, and E format types are supported.

   Parsing will fail in some unrealistic cases described in
   :func:`format.Format.parse()<filefinder.format.Format.parse>`.


Optional property
#################

The option property can achieve two different features. If the flag ``:opt`` is
present, this will append a '*?*' to the group regex, making it 'optional'.

If two options are indicated as ``:opt=A:B``, the regex will be set as an OR
between the two options ``(A|B)``. The group can now be fixed using a boolean,
that will fix the option B if true, A if false.
Either options can be left blank.

See thoses examples::

  >>> Finder('', "foo_%(bar:fmt=d:opt).txt").get_regex()
  'foo_(-?\d+)?.txt'

  >>> f = Finder('', "foo%(bar:opt=:_yes).txt")
  >>> f.get_regex()
  'foo(|_yes)'
  >>> f.fix_groups(bar=True)
  ... f.get_regex()
  'foo_yes'


Custom regex
############

Finally, one can directly use a regular expression. This will supersede
the default regex, or the one generated from the format string if specified.

It can be done like so::

  idx_%(idx:rgx=\d+?)

Discard keyword
###############

:doc:`Information can be retrieved<retrieve_values>` from the matches in the
filename, but one might discard a group so that it is not used.
For example for a file of weekly averages with a filename indicating the start
and end dates of the average, we might want to only recover the starting date::

  sst_%(x)-%(x:discard)


.. note::

   By default, when :doc:`fixing a group to a value<fix_groups>`, discarded
   groups will not be fixed. This can be deactivated with the ``fix_discard``
   keyword.


Regex outside groups
======================

By default, special characters (``()[]{}?*+-|^$\\.&~# \t\n\r\v\f``) outside of
groups are escaped, and thus not interpreted as a regular expression.
To use regular expressions outside of groups, it is necessary to activate the
``use_regex`` argument when creating the Finder object.

.. note::

   When using regex outside groups, :func:`Finder.make_filename` won't
   work.


Obtaining files
===============

Files can be retrieved with the :func:`Finder.get_files` function, or
the :attr:`Finder.files` attribute. Both will scan the directory for files
if it has not been done yet.
The 'files' attribute also stores the matches. See :ref:`Retrieve information`
for details on how matches are stored.

:func:`Finder.get_files` can also return nested lists of filenames.
This is aimed to work with :func:`xarray.open_mfdataset`,
which will merge files in a specific order when supplied a nested list of files.

To this end, one must specify group names to the `nested` argument of the same
function. The rightmost group will correspond to the innermost level.

An example is available in the :ref:`examples<Nested files>`.
