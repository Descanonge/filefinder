
Handling dates
--------------

When working with dates, it is necessary to deal with multiple individual
elements: year, month, day, etc. The package tries to make this easier by
allowing to refer to multiple elements as a single pseudo-group.

Date groups
===========

When creating groups from a pattern, FileFinder may consider some groups as
corresponding to a specific **date element** depending on their name, namely if:

- the name is of the form ``<date name>__<date element>`` (double underscore)
- the name is a registered date element (then date name is "date")

The date element will dictate the regex and format string used for that group
(unless overridden by the :ref:`fmt<fmt>` and :ref:`rgx<rgx>` properties).
Multiple groups with the same date name can be managed as a single pseudo-group.
For instance when fixing::

    finder = Finder("%(Y)-%(m)-%(d).txt")
    finder.fix(date=datetime(2000, 1, 1))
    # is equivalent to
    finder.fix(Y=2000, m=1, d=1)

    finder = Finder("%(start:Y)-%(start:m)-%(start:d).txt")
    finder.fix(start=datetime(2000, 1, 1))
    # is equivalent to
    finder.fix(start__Y=2000, start__m=1, start__d=1)

.. note::

   Creating many date groups can be a bit verbose, so the function
   :func:`.make_date_groups` helps mitigate this problem::

        >>> make_date_groups("%Y%m%d", name="start")
        "%(start__Y)%(start__m)%(start__d)"
        >>> make_date_groups("%Y-%m-%d %H:%M:%S")
        "%(Y)%(m)%(d) %(H):%(M):%(S)"

.. _date_elements:

Date elements
=============

FileFinder defines a number of available date elements that mostly follow the
specification of :ref:`strftime-strptime-behavior` and `strftime
<https://linux.die.net/man/3/strftime>`__. In particular ``F``, ``T``, and ``x``
are different from strftime definitions.

.. include:: _date_elements_table.rst

.. rubric:: Implementation and extension

Date elements are defined by a subclass of :class:`.DateElement` that define
their name, default regex, format, and some other information. In particular,
:meth:`.DateElement.datetime_to_value` extracts the element value from a
datetime object.

.. warning::

    :meth:`~.DateElement.datetime_to_str` extracts the value and format it
    according to the element *default format*. Group objects should extract the
    value and format it using their own (possibly user-defined) format string.

.. tip::

   :func:`.datetime_to_value` and :func:`.datetime_to_str` are convenience
   wrappers around those methods.


More elements can added or replaced easily: any subclass that defines a :attr:`~.DateElement.key` attribute will be
registered in :attr:`~.DateElement.ELEMENTS` and be available with
:meth:`.DateElement.get`. It will automatically be used in group definition and
date parsing.
Existing date elements objects can also be directly modified. For instance to
change the default regex: ``DateElement.get("Y").regex = ...``

.. _date-parsing:

Date parsing
============

FileFinder can create :class:`~datetime.datetime` objects from matches
corresponding to date groups. For instance::

    finder = Finder("%(Y)_%(m)_%(d).txt")
    filename = "2026_11_20.txt"
    matches = finder.find_matches(filename)
    matches["date"]  # a datetime object

Or when scanning from disk::

    matches = finder.matches[0]
    matches["date"]

The parsing is managed by :class:`.DateParser` that essentially prepares
elements before sending them to :meth:`datetime.datetime.strptime`. Some
elements may not be available on all platforms, see
:ref:`strftime-strptime-behavior`.

If a timestamp element ``s`` is present, the timezone ``z`` will be parsed
separately and the parser will use :meth:`~datetime.datetime.fromtimestamp` and
ignore all other elements. Parsing may not be accurate to the microsecond when
years are too far from the epoch.

If multiple groups have different values for the same element, an exception will
be raised. However, strptime does not check for the coherence of multiple
elements. For instance, if elements ``Ymd`` and ``j`` correspond to different
dates, one of them will be chosen and the other ignored (as far as I know, this
is undefined behavior).

.. _default_date:

Default date
++++++++++++

The filename may be missing information to fully reconstruct the date. Missing
information can be specified with the ``default_date`` argument.
It can be:

- a datetime object from which will be extracted elements ``Ymd`` for a :class:`~.datetime.date` and ``YmdHMSf`` for a :class:`~.datetime.datetime`.
  If the object is offset-aware, the timezone info `z` will also be extracted.
- a mapping containing any elements, as a string used directly or a value
  formatted appropriately. They will complete default elements corresponding to
  1970-01-01 00:00:00 (naive).

For instance: ``default_date=dt.datetime(1950, 1, 1)``, or to get offset-aware
objects ``default_date={"tzinfo": dt.UTC}``.

Timezone
++++++++

Filefinder considers :ref:`naive <datetime-naive-aware>` datetime objects (that
do not have timezone information specified) as UTC.

Unless a match contains timezone information (``%(z)``) or the `default_date`
has been given `tzinfo`, the returned date will be naive. Filefinder considers
naive objects as UTC, so if no timezone information is available it will parse
everything as if UTC.

Multi-element composition
+++++++++++++++++++++++++

To parse a date from the week day and week number, the parser needs both
information on the day of the week (elements ``a, A, u`` or ``w``) and the week
number (elements ``U`` or ``W``). If only one part of the information is
present:

- If other groups contain information about the month and day, the week part
  will simply be ignored. For instance the pattern ``"%(Y)%(m)%(d)_%(a)"``
  ("20261025_Sun") will ignore the information about the week day, and it will
  not check the day of week is coherent with the rest of the date.
- Otherwise, the parser will raise an exception. You may use the default date to
  supply the missing elements.

Similarly, when parsing the hour from a 12-hour clock, the parser will need
element ``I`` and either ``p`` or ``P``, and unless the hour can be inferred
from another element an exception will be raised.

Locale
++++++

The parser uses the current time locale. It only intervenes in the names of
months and week days. By using :meth:`.DateElement.prepare` any locale could be
passed as argument, open an issue if that is of interest to you.

Preparing elements
+++++++++++++++++++

Some date elements need some pre-processing before being sent to
:meth:`~datetime.datetime.strptime`. The :meth:`.DateElement.prepare` method
takes the matching string of that element and return a dictionary of any other
element(s) that can be used by strptime. This will also be applied to the
formatted default date elements.

For instance, ``T`` is slightly different from what strptime expects, so it is
prepared into ``{"H": "HH", "M": "MM", "S": "SS"}``.
