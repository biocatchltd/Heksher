from pytest import mark, raises

from heksher.db_logic.util import inline_sql, supersequence_new_elements


@mark.parametrize('a,b,new', [
    ('abcde', 'acd', 'be'),
    ('abc', '', 'abc'),
    ('abc', 'abc', ''),
    ('abcde', 'abc', 'de'),
    ('abcde', 'cde', 'ab'),
    ('abcde', 'bcd', 'ae')
])
def test_issupersequence(a, b, new):
    ss = supersequence_new_elements(a, b)
    assert ss is not None
    expected_new = tuple((n, a.find(n)) for n in new)
    assert ss == expected_new


@mark.parametrize('a,b', [
    ('abc', 'abcd'),
    ('abc', 'cb'),
    ('', 'a'),

])
def test_is_not_supersequence(a, b):
    ss = supersequence_new_elements(a, b)
    assert ss is None


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
