
.. currentmodule:: filefinder

Pattern
-------

The pattern specifies the structure of the filenames relative to the root
directory. Parts that vary from file to file are indicated by **groups**,
enclosed by parenthesis and preceded by '%'. They are represented by the
:class:`~group.Group` class.

Each group definition starts with a :ref:`name<name>`, and is then followed by
multiple optional properties, separated by colons (in no particular order):

+---------------+--------------------------+--------------------------------+
|Property       |Format                    |Description                     |
+===============+==========================+================================+
|:ref:`Format   |``:fmt=<format string>``  |Use a python format string to   |
|string<fmt>`   |                          |match this group in filenames.  |
+---------------+--------------------------+--------------------------------+
|:ref:`Boolean  |``:bool=<true>[:<false>]``|Choose between two alternatives.|
|format<bool>`  |                          |The second option (false) can be|
|               |                          |omitted.                        |
+---------------+--------------------------+--------------------------------+
|:ref:`Custom   |``:rgx=<custom regex>``   |Specify a custom regular        |
|regex<rgx>`    |                          |expression directly.            |
|               |                          |                                |
+---------------+--------------------------+--------------------------------+
|:ref:`Optional |``:opt``                  |Mark the group as optional.     |
|flag<opt>`     |                          |                                |
+---------------+--------------------------+--------------------------------+
|:ref:`Discard  |``:discard``              |Discard the value parsed from   |
|flag<discard>` |                          |this group when retrieving      |
|               |                          |information.                    |
+---------------+--------------------------+--------------------------------+

So for instance, we can specify a filename pattern that will match an integer
padded with zeros, followed by two possible options::

   parameter_%(param:fmt=04d)_type_%(type:bool=foo:bar).txt
    -> parameter_0012_type_foo.txt
    -> parameter_2020_type_bar.txt


.. note::

   Groups are uniquely identified by their index in the pattern (starting at 0)
   and can share the same name. When using a name rather than an index, some
   functions may return more than one result if they are multiple groups with
   that name.

.. warning::

   Groups are first found in the pattern by looking at matching
   parentheses. The pattern should thus have balanced parentheses or
   unexpected behavior can occur.


.. _name:

Name
====

The name of the group will dictate the regex and format string used for that
group (unless overridden the 'fmt' and 'rgx' properties).
The :attr:`Group.DEFAULT_GROUPS<group.Group.DEFAULT_GROUPS>`
class attribute will make the correspondence between name and regex:

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

Most of them are related to dates and follow the specification of
:ref:`strftime-strptime-behavior` and `strftime
<https://linux.die.net/man/3/strftime>`__.

A letter preceded by a percent sign '%' in the regex will be recursively
replaced by the corresponding name in the table. This can be used in the
custom regex. This still counts as a single group and its name will not
be changed, only the regex.
So ``%x`` will be replaced by ``%Y%m%d``, in turn replaced by ``\d{4}\d\d\d\d``.
A percentage character in the regex is escaped by another percentage ('%%').


.. _fmt:

Format string
=============

All the possible use cases are not covered in the table above. A simple way to
specify a group is by using a format string following the
`Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__.
This will automatically be transformed into a regular expression.

Having a format specified has other benefits: it can be used to convert values
into strings to generate a filename from parameters values (using
:func:`Finder.make_filename<finder.Finder.make_filename>`), or vice-versa to
parse filenames matches into parameters values.

It's easy as ``scale_%(scale:fmt=.1f)`` which will find files such as
``scale_15.0`` or ``scale_-5.6``. Because we know how to transform a value into
a string we can fix the group directly with a value::

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

   Parsing of numbers will fail in some ambiguous (and quite unrealistic) cases
   that involves alignment padding with numbers or the minus signs. Creating a
   format object where we can't unambiguously remove the padding character is
   not allowed and will raise a :class:`~format.DangerousFormatError`.

   Similarly, for a string format (s) it can be impossible to separate correctly
   the alignment padding character (the "fill") from the actual value. Here the
   user is entrusted with making sure that the fill character does not appear
   in the value (or not at its beginning or end at least).


.. _bool:

Boolean format
==============

The boolean format allows to easily select between two options. It is specified
as ``:bool=<true>[:<false>]``. The second option (false), can be omitted.

Both ``<true>`` and ``<false>`` here refer to regular expressions. Don't forget
to escape any special characters!

Here are a couple of examples. ``my_file%(special:bool=_special).txt`` would
match both ``my_file.txt`` and ``my_file_special.txt``. We could select only
'special' files using ``finder.fix_groups(special=True)``.

We can also specify both options with ``my_file_%(good:bool=good:bad).txt``, and
select either like so ::

    >>> finder.make_filename(kind=True)
    my_file_good.txt
    >>> finder.make_filename(kind=False)
    my_file_bad.txt


.. _opt:

Optional flag
=============

The optional flag ``:opt`` mark the group as an optional part of the pattern. In
effect, it appends a ``?`` to the group regular expression. It does not affect
the group in other ways.


.. _rgx:

Custom regex
============

Finally, one can directly use a regular expression. This will supersede
the default regex, or the one generated from the format string if specified.

It can be done like so::

  idx_%(idx:rgx=\d+?)

.. _discard:

Discard keyword
===============

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
====================

By default, special characters (``()[]{}?*+-|^$\\.&~# \t\n\r\v\f``) outside of
groups are escaped, and thus not interpreted as a regular expression.
To use regular expressions outside of groups, it is necessary
to pass ``use_regex=True`` when creating the Finder object.

.. note::

   When using regex outside groups,
   :func:`Finder.make_filename<finder.Finder.make_filename>` won't work.
