from pytest import mark, raises

from heksher.db_logic.util import is_supersequence, inline_sql


@mark.parametrize('a,b,new', [
    ('abcde', 'acd', 'be'),
    ('abc', '', 'abc'),
    ('abc', 'abc', ''),
    ('abcde', 'abc', 'de'),
    ('abcde', 'cde', 'ab'),
    ('abcde', 'bcd', 'ae')
])
def test_issupersequence(a, b, new):
    ss = is_supersequence(a, b)
    assert ss
    expected_new = tuple((n, a.find(n)) for n in new)
    assert ss.new_elements == expected_new


@mark.parametrize('a,b', [
    ('abc', 'abcd'),
    ('abc', 'cb'),
    ('', 'a'),

])
def test_is_not_supersequence(a, b):
    ss = is_supersequence(a, b)
    assert not ss


@mark.parametrize('x', [
    "a'",
    "' OR '1' = '1",
    "-- DROP TABLE x",
    ''
])
def test_invalid_inline_sql(x):
    with raises(AssertionError):
        inline_sql(x)


@mark.parametrize('x', [
    "a",
    "abra cadabra",
    'DROP TABLE x',
    "DROP TABLE x at 9 oclock"
])
def test_valid_inline_sql(x):
    assert inline_sql(x) == "'" + x + "'"
