"""Generate regex from string format, and parse strings.

Parameters of the format-string are retrieved.
See `Format Mini Language Specification
<https://docs.python.org/3/library/string.html#formatspec>`__.

Thoses parameters are then used to generate a regular expression, or to parse
a string formed from the format.

Only 's', 'd', 'f', 'e' and 'E' formats types are supported.

The width of the format string is not respected when matching with a regular
expression.

The parsing is quite naive and can fail on some cases.
See :func:`Format.parse` for details.

The regex generation and parsing are tested in `tests/unit/test_format.py`.
"""

# This file is part of the 'filefinder' project
# (http://github.com/Descanonge/filefinder) and subject
# to the MIT License as defined in the file 'LICENSE',
# at the root of this project. © 2021 Clément Haëck

import re
from typing import Any, Union


def autoprop(*props):
    """Generate properties for class.

    Properties all link to `cls.params` dictionnary.
    """
    def factory_get(name):
        def getter(self):
            return self.params.get(name, None)
        return getter

    def factory_set(name):
        def setter(self, value):
            self.params[name] = value
        return setter

    def decorator(cls):
        for name in props:
            prop = property(factory_get(name), factory_set(name))
            setattr(cls, name, prop)
        return cls

    return decorator


@autoprop('fill', 'align', 'sign', 'alternate', 'zero',
          'width', 'grouping', 'precision', 'type')
class Format:
    """Parse a format string.

    Out of found parameters:
    - generate regular expression
    - format value
    - parse string into value

    Parameters
    ----------
    fmt: str
        Format string.
    """

    ALLOWED_TYPES = 'fdeEs'

    def __init__(self, fmt: str):
        self.fmt = fmt
        self.params = {}
        self.parse_params(fmt)
        self.set_defaults()

    def parse_params(self, format: str):
        """Parse format parameters."""
        p = (r"((?P<fill>.)?(?P<align>[<>=^]))?"
             r"(?P<sign>[-+ ])?(?P<alternate>#)?"
             r"(?P<zero>0)?(?P<width>\d+?)?"
             r"(?P<grouping>[,_])?"
             r"(?P<precision>\.\d+?)?"
             r"(?P<type>[a-zA-Z])")
        m = re.fullmatch(p, format)
        if m is None:
            raise ValueError("Format spec not valid.")
        self.params = m.groupdict()
        if not self.type or self.type not in self.ALLOWED_TYPES:
            raise ValueError('format spec %r not supported' % self.type)

    def set_defaults(self):
        """Set parameters defaults values."""
        if self.type in 'dfeE':
            defaults = dict(
                align='>',
                fill=' ',
                sign='-',
                width='0',
                precision='.6'
            )
            self.alternate = self.alternate == '#'
            self.zero = self.zero == '0'
            if self.align is None and self.zero:
                self.fill = '0'
                self.align = '='
            for k, v in defaults.items():
                if self.params[k] is None:
                    self.params[k] = v
            self.width = int(self.width)
            self.precision = int(self.precision[1:])

    def format(self, value: Any) -> str:
        """Return formatted string."""
        return '{{:{}}}'.format(self.fmt).format(value)

    def generate_expression(self) -> str:
        """Generate regex from format string."""
        if self.type == 'f':
            return self.generate_expression_f()
        if self.type == 'd':
            return self.generate_expression_d()
        if self.type == 's':
            return self.generate_expression_s()
        if self.type in 'eE':
            return self.generate_expression_e()

    def parse(self, s: str) -> Union[str, int, float]:
        """Parse string generated with format.

        This simply use int() and float() to parse strings. Those are thrown
        off when using fill characters (other than 0), or thousands groupings,
        so we remove these from the string.

        Parsing will fail when using the '-' fill character on a negative
        number, or when padding with numbers. If you use such formats, please
        contact me to explain me why in the hell you do.
        """
        if self.type == 'd':
            return self.parse_d(s)
        if self.type in 'feE':
            return self.parse_f(s)
        if self.type == 's':
            return s

    def generate_expression_s(self) -> str:
        return '.*?'

    def generate_expression_d(self) -> str:
        rgx = self.get_left_point()
        return self.insert_in_alignement(rgx)

    def generate_expression_f(self) -> str:
        rgx = self.get_left_point()
        rgx += self.get_right_point()
        return self.insert_in_alignement(rgx)

    def generate_expression_e(self) -> str:
        rgx = r'\d'
        rgx += self.get_right_point()
        rgx += r'{}[+-]\d+'.format(self.type)
        return self.insert_in_alignement(rgx)

    def insert_in_alignement(self, rgx: str) -> str:
        fill_rgx = ''
        if self.width > 0:
            fill_rgx += '{}*'.format(re.escape(self.fill))
        out_rgx = ''

        if self.align in '>^':
            out_rgx += fill_rgx

        out_rgx += self.get_sign()

        if self.align == '=':
            out_rgx += fill_rgx

        out_rgx += rgx

        if self.align in '<^':
            out_rgx += fill_rgx

        return out_rgx

    def get_sign(self) -> str:
        """Get sign regex."""
        if self.sign == '-':
            rgx = '-?'
        elif self.sign == '+':
            rgx = r'[+-]'
        elif self.sign == ' ':
            rgx = r'[\s-]'
        else:
            raise KeyError("Sign not in {+- }")
        return rgx

    def get_left_point(self) -> str:
        """Get regex for numbers left of decimal point."""
        if self.grouping is not None:
            rgx = r'\d?\d?\d(?:{}\d{{3}})*'.format(self.grouping)
        else:
            rgx = r'\d+'
        return rgx

    def get_right_point(self) -> str:
        rgx = ''
        if self.precision != 0 or self.alternate:
            rgx += r'\.'
        if self.precision != 0:
            rgx += r'\d{{{:d}}}'.format(self.precision)
        return rgx

    def parse_d(self, s: str) -> int:
        """Parse integer from formatted string. """
        return int(self.remove_special(s))

    def parse_f(self, s: str) -> float:
        """Parse float from formatted string."""
        return float(self.remove_special(s))

    def remove_special(self, s: str) -> str:
        """Remove special characters.

        Remove characters that throw off int() and float() parsing.
        Namely fill and grouping characters.
        Will remove fill, except when fill is zero (parsing functions are
        okay with that).
        """
        to_remove = [',', '_']  # Any grouping char
        if self.fill != '0':
            to_remove.append(re.escape(self.fill))
        pattern = '[{}]'.format(''.join(to_remove))
        return re.sub(pattern, '', s)
