
.. currentmodule:: filefinder

Pattern
-------

The pattern specifies the structure of the filenames relative to the root
directory. Parts that vary from file to file are indicated by **groups**,
enclosed by parenthesis and preceded by '%'.

Each group definition starts with a :ref:`name<name>`, and is then followed by
multiple optional properties, separated by colons (in no particular order):


.. table::
   :widths: grid

   +--------------------+--------------------------+--------------------------------+
   |Property            |Format                    |Description                     |
   +====================+==========================+================================+
   |:ref:`Format        |``:fmt=<format string>``  |Use a python format string to   |
   |string<fmt>`        |                          |match filenames and format      |
   |                    |                          |values.                         |
   +--------------------+--------------------------+--------------------------------+
   |:ref:`Boolean       |``:bool=<true>[:<false>]``|Choose between two alternatives.|
   |format<bool>`       |                          |The second option (false) can be|
   |                    |                          |omitted when empty.             |
   +--------------------+--------------------------+--------------------------------+
   |:ref:`Custom        |``:rgx=<custom regex>``   |Specify a custom regular        |
   |regex<rgx>`         |                          |expression directly.            |
   |                    |                          |                                |
   +--------------------+--------------------------+--------------------------------+
   |:ref:`Optional      |``:opt``                  |Mark the group as optional.     |
   |flag<opt>`          |                          |                                |
   +--------------------+--------------------------+--------------------------------+
   |:ref:`pre-post`     |``:pre=<prefix>`` et      |Add prefix or suffix to the     |
   |                    |``:post=<suffix>``        |group.                          |
   +--------------------+--------------------------+--------------------------------+

So for instance, we can specify a filename pattern that will match an integer
padded with zeros, followed by two possible options::

   >>> "parameter_%(param:fmt=04d)_%(type:bool=foo:bar).txt"
   parameter_0012_foo.txt
   parameter_2020_bar.txt

Groups are found within the pattern using the parameter
:class:`group_delimiters<.Finder>`, a tuple of the form 'prefix, start, end' (by
default ``('%', '(', ')')``). The *start* and *end* must be balanced (no
parenthesis left open for instance). The prefix can be empty. For instance, by
passing ``group_delimiters=('', '{', '}')``, the following pattern becomes
valid: ``"parameter_{param:fmt=04}_{Y}-{m}-{d}.txt"``.

.. _name:

Name
====

The name can be anything (excluding colons ':'). It will be used to refer to
that group when fixing groups or retrieving matches.

.. note::

   Groups are uniquely identified by their index in the pattern (starting at 0)
   and can share the same name. When using a name rather than an index, some
   functions may return more than one result if they are multiple groups with
   that name.

Filefinder tries to simplify working with dates (see :ref:`dates`). To create a
group that corresponds to a date element you can use the following name
structure ``<date name>__<date element>`` (with a double underscore): for
instance ``start__Y``. The date element must be contained in the table below.
It will dictate the regex and format string used for that group (unless
overridden by the :ref:`fmt<fmt>` and :ref:`rgx<rgx>` properties). By having
multiple groups with the same date name they can be managed as a single
pseudo-group.

The date name can be omitted, in that case it will default to 'date', but the
group name will remain unchanged (*ie* "%(Y)" will be not be available as
"date__Y").

+------+-------------------+---------------------+--------+
| Name |                   | Regex               | Format |
+======+===================+=====================+========+
| Y    | Year (YYYY)       | \\d{4}              |    04d |
+------+-------------------+---------------------+--------+
| m    | Month (MM)        | \\d\\d              |    02d |
+------+-------------------+---------------------+--------+
| d    | Day of month (DD) | \\d\\d              |    02d |
+------+-------------------+---------------------+--------+
| j    | Day of year (DDD) | \\d{3}              |    03d |
+------+-------------------+---------------------+--------+
| B    | Month name        | \\w+                |      s |
+------+-------------------+---------------------+--------+
| H    | Hour 24 (HH)      | \\d\\d              |    02d |
+------+-------------------+---------------------+--------+
| M    | Minute (MM)       | \\d\\d              |    02d |
+------+-------------------+---------------------+--------+
| S    | Seconds (SS)      | \\d\\d              |    02d |
+------+-------------------+---------------------+--------+
| F    | Date (YYYY-MM-DD) | \\d{4}-\\d\\d-\\d\\d|      s |
+------+-------------------+---------------------+--------+
| x    | Date (YYYYMMDD)   | \\d{8}              |    08d |
+------+-------------------+---------------------+--------+
| X    | Time (HHMMSS)     | \\d{6}              |    06d |
+------+-------------------+---------------------+--------+

This follow the specification of :ref:`strftime-strptime-behavior` and `strftime
<https://linux.die.net/man/3/strftime>`__.

.. note::

   Creating many date groups can be a bit verbose, so the function
   :func:`.make_date_groups` helps mitigate this problem::

        >>> make_date_groups("%Y%m%d", name="start")
        "%(start__Y)%(start__m)%(start__d)"
        >>> make_date_groups("%Y-%m-%d %H:%M:%S")
        "%(Y)%(m)%(d) %(H):%(M):%(S)"

.. _fmt:

Format string
=============

A simple way to specify a group is by using a format string following the
`Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__. This will
automatically be transformed into a regular expression.
It's easy as ``scale_%(scale:fmt=.1f)`` which will find files such as
``scale_15.0`` or ``scale_-5.6``.

Because we know how to transform a value into a string we can fix the group
directly with a value::

  finder.fix(scale=15.)
  # or
  finder.make_filename(scale=2.5)

In the opposite direction, we can retrieve a value from a filename::

  >>> matches = finder.find_matches('scale_2.5')
  >>> print(matches['scale'])
  2.5  # a float

If the format is never specified, it defaults to a ``s`` format.

.. warning::

   Only s, d, f, e, and E format types are supported.

   Parsing of numbers will fail in some ambiguous (and quite unrealistic) cases
   that involves alignment padding with numbers or the minus signs. Creating a
   format object where we can't unambiguously remove the padding character is
   not allowed and will raise a :class:`~format.DangerousFormatError`.

   Similarly, for a string format (s) it can be impossible to correctly separate
   the alignment padding character (the "fill") from the actual value. Here the
   user is entrusted with making sure the format fill character is adapted to
   the expected values to parse.


.. _bool:

Boolean format
==============

The boolean format allows to easily select between two *strings*. It is
specified as ``:bool=<true>[:<false>]``. The second option (false) can be
omitted if empty.

Here are a couple of examples. ``my_file%(special:bool=_special).txt`` would
match both ``my_file.txt`` and ``my_file_special.txt``. We would select only
'special' files using ``finder.fix(special=True)``.

We can also specify both options with ``my_file_%(is_good:bool=good:bad).txt``, and
select either like so:

    >>> finder.make_filename(is_good=True)
    my_file_good.txt
    >>> finder.make_filename(is_good=False)
    my_file_bad.txt


.. _opt:

Optional flag
=============

The optional flag ``:opt`` marks the group as an optional part of the pattern.
It can be thought as appending a ``?`` to the group regular expression.

For instance, ``A%(param:fmt=d).txt`` would match "A.txt", "A0.txt", etc.
If the group is not present, the parsed value will be `None`. When fixed to
the value `None`, this will only match files without the group (*ie* "A.txt")

An optional group does not have to be fixed when :ref:`generating a
filename<create-filenames>`.

.. _pre-post:

Prefix and suffix
=================

The prefix and suffix will be added to formatted values, as well as to the group
regex. They will not be added when fixing to a string (strings are fixed as-is).
They are removed before parsing values.

It can be useful when a group is optional, for instance
``A%(idx:fmt=d:pre=_:opt).txt`` would match "A.txt" and "A_0.txt", and correctly
parse the value as an integer when present.

.. _rgx:

Custom regex
============

Finally, one can directly use a regular expression. This will supersede
the default regex, or the one generated from the format string if specified.

It can be done like so::

  idx_%(idx:rgx=\d+?)


.. important::

   Finder relies on the indices of matching groups. There must be as many groups
   in the pattern as matching groups in the final regular expression. Therefore
   only use non-capturing groups ``(?:...)``.

Regex outside groups
====================

By default, special characters (``()[]{}?*+-|^$\\.&~# \t\n\r\v\f``) outside of
groups are escaped, and thus not interpreted as a regular expression.
To use regular expressions outside of groups, it is necessary
to pass ``use_regex=True`` when creating the Finder object.

.. note::

   When using regex outside groups,
   :func:`Finder.make_filename<finder.Finder.make_filename>` won't work.
