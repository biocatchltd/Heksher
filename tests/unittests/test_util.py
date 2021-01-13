from pytest import mark

from heksher.db_logic.util import is_supersequence


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
