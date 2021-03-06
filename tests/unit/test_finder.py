"""Test main features. """

import itertools
from os import path
from datetime import datetime, timedelta

from filefinder import Finder

import pytest

try:
    import pyfakefs
except ImportError:
    _pyfakefs = False
else:
    _pyfakefs = True


def assert_pregex(pregex, regex):
    finder = Finder('', pregex)
    assert finder.regex == regex


def test_date_matchers():
    assert_pregex('test_%(x).ext', r'test_(\d{4}\d\d\d\d)\.ext')
    assert_pregex('test_%(Y).ext', r'test_(\d{4})\.ext')
    assert_pregex('test_%(Y)-%(m)-%(d).ext',
                  r'test_(\d{4})\-(\d\d)\-(\d\d)\.ext')


def test_multiple_matchers():
    finder = Finder('', 'test_%(m)_%(d)')
    assert finder.n_matchers == 2
    assert finder.matchers[0].name == 'm'
    assert finder.matchers[1].name == 'd'


def test_custom_regex():
    assert_pregex('test_%(Y:rgx=[a-z]*?)', 'test_([a-z]*?)')
    assert_pregex('test_%(Y:fmt=d:rgx=[a-z]*?)', 'test_([a-z]*?)')


def test_format_regex():
    assert_pregex('test_%(Y:fmt=d)', r'test_(-?\d+)')
    assert_pregex('test_%(Y:fmt=a>5d)', r'test_(a*-?\d+)')
    assert_pregex('test_%(Y:fmt=a<5d)', r'test_(-?\d+a*)')
    assert_pregex('test_%(Y:fmt=a^5d)', r'test_(a*-?\d+a*)')
    assert_pregex('test_%(Y:fmt=05.3f)', r'test_(-?0*\d+\.\d{3})')
    assert_pregex('test_%(Y:fmt=+05.3f)', r'test_([+-]0*\d+\.\d{3})')
    assert_pregex('test_%(Y:fmt=.2e)', r'test_(-?\d\.\d{2}e[+-]\d+?\d)')
    assert_pregex('test_%(Y:fmt=.2E)', r'test_(-?\d\.\d{2}E[+-]\d+?\d)')


def test_name_group():
    def assert_group_name(pregex, names):
        finder = Finder('', pregex)
        for m, (group, name) in zip(finder.matchers, names):
            assert(m.group == group)
            assert(m.name == name)

    assert_group_name('test_%(foo:bar:fmt=.2f)', [('foo', 'bar')])
    assert_group_name(r'test_%(foo:bar:fmt=.2f:rgx=\d)', [('foo', 'bar')])
    assert_group_name('test_%(foo:bar:fmt=d)_%(foo2:bar2:fmt=s)',
                      [('foo', 'bar'), ('foo2', 'bar2')])


def test_optional():
    assert_pregex('test_%(m:opt)', r'test_(\d\d)?')
    assert_pregex('test_%(lol:opt=A:B)', 'test_(A|B)')


def test_fix_matcher_string():
    finder = Finder('', 'test_%(m)_%(c:fmt=.1f)')
    finder.fix_matcher(0, '01')
    finder.fix_matcher(1, r'11\.1')
    assert finder.regex == r'test_(01)_(11\.1)'


def test_fix_matcher_value():
    finder = Finder('', 'test_%(m)_%(c:fmt=.1f)_%(b:opt=A:B)')
    finder.fix_matcher(0, 1)
    finder.fix_matcher(1, 11)
    finder.fix_matcher(2, True)
    assert finder.regex == r'test_(01)_(11\.0)_(B)'


def test_get_matchers():
    def assert_get_matchers(finder, key, indices):
        assert indices == [m.idx for m in finder.get_matchers(key)]

    finder = Finder('', 'test_%(time:m)_%(c:fmt=.1f)_%(time:d)_%(d)')
    assert_get_matchers(finder, 'm', [0])
    assert_get_matchers(finder, 'c', [1])
    assert_get_matchers(finder, 'd', [2, 3])
    assert_get_matchers(finder, 'time:d', [2])


def test_get_filename():
    finder = Finder('', 'test_%(m)_%(c:fmt=.2f)_%(b:opt=:yes)')
    finder.fix_matchers(m=1)
    assert finder.get_filename(c=5, b=True) == 'test_01_5.00_yes'


dates = [datetime(2000, 1, 1) + i*timedelta(days=15) for i in range(50)]
params = [-1.5, 0., 1.5]
options = [False, True]


@pytest.mark.skipif(not _pyfakefs, reason='pyfakefs not installed')
def test_file_scan(fs):
    datadir = '/data'
    fs.create_dir('/data')
    files = []
    for d, p, o in itertools.product(dates, params, options):
        filename = '{}/test_{}_{:.1f}{}.ext'.format(
            d.year, d.strftime('%F'), p, '_yes' if o else '')
        files.append(filename)
        fs.create_file(path.join(datadir, filename))
    files.sort()

    finder = Finder(datadir,
                    ('%(Y)/test_%(Y)-%(m)-%(d)_'
                     '%(param:fmt=.1f)%(option:opt=:_yes).ext'))
    assert len(finder.files) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref
