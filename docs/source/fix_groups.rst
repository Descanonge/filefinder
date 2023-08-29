
.. currentmodule:: filefinder.finder

Fix groups
============

The package allows to dynamically change the regular expression easily. This is
done by replacing groups in the regular expression by a given string, using
the :func:`Finder.fix_group` and :func:`Finder.fix_groups` methods.

Groups to replace can be selected either by their index in the filename pattern
(starting from 0), or by their name. If using a group name , multiple groups
can be fixed to the same value at once.

If the corresponding group·s have a format specified, and the given value
is not already a string, it will be formatted.
If using a list of values, the strings (given or formatted) will be joined by
a regex *OR* (``(value1|value2|...)``).

If a string is given, special characters will **not** be escaped.
This allows to specify regular expressions.
On the contrary, for a formatted value special characters will be escaped::

  finder.fix_group('foo', '[a-z]+')  # will be kept as is
  finder.fix_group('bar', 3.)  # will be formatted as '3\.0'

For a more practical example, when using the following pattern::

  '%(time:m)/SST_%(time:Y)%(time:m)%(time:d).nc'

we can keep only the files corresponding to january using any of::

  finder.fix_group(0, 1)
  finder.fix_group('m', 1)

We could also select specific days using a list::

  finder.fix_group('d', [1, 3, 5, 7])
