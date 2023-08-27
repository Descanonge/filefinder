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


def assert_pattern(pattern, regex):
    finder = Finder('', pattern)
    assert finder.get_regex() == regex


def test_date_groups():
    assert_pattern('test_%(x).ext', r'test_(\d{4}\d\d\d\d)\.ext')
    assert_pattern('test_%(Y).ext', r'test_(\d{4})\.ext')
    assert_pattern('test_%(Y)-%(m)-%(d).ext',
                  r'test_(\d{4})\-(\d\d)\-(\d\d)\.ext')


def test_multiple_groups():
    finder = Finder('', 'test_%(m)_%(d)')
    assert finder.n_groups == 2
    assert finder._groups[0].name == 'm'
    assert finder._groups[1].name == 'd'


def test_custom_regex():
    assert_pattern('test_%(Y:rgx=[a-z]*?)', 'test_([a-z]*?)')
    assert_pattern('test_%(Y:fmt=d:rgx=[a-z]*?)', 'test_([a-z]*?)')


def test_format_regex():
    assert_pattern('test_%(Y:fmt=d)', r'test_(-?\d+)')
    assert_pattern('test_%(Y:fmt=a>5d)', r'test_(a*-?\d+)')
    assert_pattern('test_%(Y:fmt=a<5d)', r'test_(-?\d+a*)')
    assert_pattern('test_%(Y:fmt=a^5d)', r'test_(a*-?\d+a*)')
    assert_pattern('test_%(Y:fmt=05.3f)', r'test_(-?0*\d+\.\d{3})')
    assert_pattern('test_%(Y:fmt=+05.3f)', r'test_([+-]0*\d+\.\d{3})')
    assert_pattern('test_%(Y:fmt=.2e)', r'test_(-?\d\.\d{2}e[+-]\d+)')
    assert_pattern('test_%(Y:fmt=.2E)', r'test_(-?\d\.\d{2}E[+-]\d+)')


def test_name_group():
    def assert_group_name(pattern, names):
        finder = Finder('', pattern)
        for m, (group, name) in zip(finder._groups, names):
            assert(m.group == group)
            assert(m.name == name)

    assert_group_name('test_%(foo:bar:fmt=.2f)', [('foo', 'bar')])
    assert_group_name(r'test_%(foo:bar:fmt=.2f:rgx=\d)', [('foo', 'bar')])
    assert_group_name('test_%(foo:bar:fmt=d)_%(foo2:bar2:fmt=s)',
                      [('foo', 'bar'), ('foo2', 'bar2')])


def test_optional():
    assert_pattern('test_%(m:opt)', r'test_(\d\d)?')
    assert_pattern('test_%(lol:opt=A:B)', 'test_(A|B)')


def test_fix_group_string():
    finder = Finder('', 'test_%(m)_%(c:fmt=.1f)')
    finder.fix_group(0, '01')
    finder.fix_group(1, r'11\.1')
    assert finder.get_regex() == r'test_(01)_(11\.1)'


def test_fix_group_value():
    finder = Finder('', 'test_%(m)_%(c:fmt=.1f)_%(b:opt=A:B)')
    finder.fix_group(0, 1)
    finder.fix_group(1, 11)
    finder.fix_group(2, True)
    assert finder.get_regex() == r'test_(01)_(11\.0)_(B)'


def test_get_groups():
    def assert_get_groups(finder, key, indices):
        assert indices == [g.idx for g in finder.get_groups(key)]

    finder = Finder('', 'test_%(m)_%(c:fmt=.1f)_%(d)_%(d)')
    assert_get_groups(finder, 'm', [0])
    assert_get_groups(finder, 'c', [1])
    assert_get_groups(finder, 'd', [2, 3])


def test_get_filename():
    root = path.join('data', 'root')
    filename_rel = 'test_01_5.00_yes'
    filename_abs = path.join(root, filename_rel)
    finder = Finder(root, 'test_%(m)_%(c:fmt=.2f)_%(b:opt=:yes)')

    # Without fix
    assert finder.get_filename(m=1, c=5, b=True) == filename_abs
    # With dictionnary
    assert finder.get_filename(dict(m=1, c=5, b=True)) == filename_abs
    # With mix
    assert finder.get_filename(dict(m=1, c=5), b=True) == filename_abs
    # Relative file
    assert finder.get_filename(relative=True, m=1, c=5, b=True) == filename_rel

    # With fix
    finder.fix_groups(m=1)
    assert finder.get_filename(c=5, b=True) == filename_abs
    assert finder.get_filename(dict(c=5), b=True) == filename_abs


dates = [datetime(2000, 1, 1) + i*timedelta(days=15) for i in range(50)]
params = [-1.5, 0., 1.5]
options = [False, True]


@pytest.mark.skipif(not _pyfakefs, reason='pyfakefs not installed')
def test_file_scan(fs):
    datadir = path.sep + 'data'
    fs.create_dir(datadir)
    files = []
    for d, p, o in itertools.product(dates, params, options):
        filename = '{}{}test_{}_{:.1f}{}.ext'.format(
            d.year, path.sep,
            d.strftime('%F'), p, '_yes' if o else '')
        files.append(filename)
        fs.create_file(path.join(datadir, filename))
    files.sort()

    finder = Finder(datadir,
                    ('%(Y){}test_%(Y)-%(m)-%(d)_'
                     '%(param:fmt=.1f)%(option:opt=:_yes).ext')
                    .format(path.sep))
    assert len(finder.files) == len(files)
    for f, f_ref in zip(finder.get_files(relative=True), files):
        assert f == f_ref
