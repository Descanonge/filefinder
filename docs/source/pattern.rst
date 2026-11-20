
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
   |:ref:`pre-post`     |``:pre=<prefix>`` and     |Add prefix or suffix to the     |
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

The name can be anything (excluding colons ``:``). It will be used to refer to
that group when fixing groups or retrieving matches.

To simplify working with dates, FileFinder may consider some groups as
corresponding to date elements (year, month, hour, etc.) depending on their
name, namely if:

- the name is of the form ``<date name>__<date element>`` (double underscore)
- the name is a registered date element (then date name is "date")

See :doc:`handling_dates` for details.

.. tip::

    As all default date elements have names with a single letter (``Y``, ``m``,
    ``d``, etc.), use multi-character group names to avoid being considered as
    a date group.

.. note::

   Groups are uniquely identified by their index in the pattern (starting at 0)
   and can share the same name. When using a name rather than an index, some
   functions may return more than one result if they are multiple groups with
   that name.


.. _fmt:

Format string
=============

A simple way to specify a group is by using a format string following the
`Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__. This will
automatically be transformed into a regular expression.
It's easy as ``scale_%(scale:fmt=.1f)`` which will match ``scale_15.0`` or
``scale_-5.6``.

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
   that involve alignment padding with numbers or the minus sign. Creating a
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

For example ``my_file%(special:bool=_special).txt`` would match both
"my_file.txt" and "my_file_special.txt". We can select only 'special'
files using ``finder.fix(special=True)``.

We can also specify both options with ``my_file_%(is_good:bool=good:bad).txt``,
and select either like so:

    >>> finder.make_filename(is_good=True)
    my_file_good.txt
    >>> finder.make_filename(is_good=False)
    my_file_bad.txt


.. _opt:

Optional flag
=============

The optional flag ``:opt`` marks the group as an optional part of the pattern.
It can be thought as appending a ``?`` to the group regular expression.

For instance, ``A%(param:fmt=d:opt).txt`` would match "A.txt" and "A0.txt".
If the group is not present, the parsed value will be `None`. When fixed to
the value `None`, this will only match files without the group (*ie* "A.txt")

An optional group does not have to be fixed when :ref:`generating a
filename<generate-filenames>`.

.. _pre-post:

Prefix and suffix
=================

The prefix and suffix will be added to formatted values, as well as to the group
regex (correctly escaped). They are removed before parsing values.

It can be useful when a group is optional, for instance
``A%(idx:fmt=d:pre=_:opt).txt`` would match "A.txt" and "A_0.txt", and correctly
parse the value as an integer when present.

.. _rgx:

Custom regex
============

Finally, one can directly specify the regular expression to use. This will
supersede the regex from a date element or the one generated from the format
string if specified.
For instance::

  idx_%(idx:rgx=\d+?)


.. important::

   Finder relies on the indices of matching groups. There must be as many groups
   in the pattern as matching groups in the final regular expression. Therefore
   only use non-capturing groups ``(?:...)``.

Regex outside groups
====================

By default, special characters (``()[]{}?*+-|^$\\.&~# \t\n\r\v\f``) outside of
groups are escaped, and thus not interpreted as a regular expression. To use
regular expressions outside of groups, it is necessary to set
:attr:`~.Finder.regex_outside_groups` to True (as a property or when creating
the Finder).

.. note::

   When using regex outside groups,
   :func:`Finder.make_filename<finder.Finder.make_filename>` won't work.
