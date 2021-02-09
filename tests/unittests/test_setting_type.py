from pytest import mark

from heksher.setting_types import setting_type


def test_primitives():
    names = ['int', 'str', 'bool', 'float']
    for n in names:
        s_type = setting_type(n)
        assert str(s_type) == n
        assert s_type == setting_type(n)
        assert all((other == n or setting_type(other) != s_type) for other in names)


@mark.parametrize('x', [
    1,
    3,
    -9,
    -4,
    10000,
    0,
    1.0,
])
def test_int_truish(x):
    s_type = setting_type('int')
    assert s_type.validate(x)


@mark.parametrize('x', [
    1.5,
    '1',
    True,
    None
])
def test_int_falsish(x):
    s_type = setting_type('int')
    assert not s_type.validate(x)


@mark.parametrize('x', [
    1,
    3,
    1.5,
    9.5,
    -158,
    -5.6,
    0.0,
    6.0
])
def test_float_truish(x):
    s_type = setting_type('float')
    assert s_type.validate(x)


@mark.parametrize('x', [
    True,
    None,
    '9.6'
])
def test_float_falsish(x):
    s_type = setting_type('float')
    assert not s_type.validate(x)


@mark.parametrize('x', [
    'hi',
    '',
    '\x00g',
])
def test_str_truish(x):
    s_type = setting_type('str')
    assert s_type.validate(x)


@mark.parametrize('x', [
    None,
    65,
    b'15'
])
def test_str_falsish(x):
    s_type = setting_type('str')
    assert not s_type.validate(x)


@mark.parametrize('x', [
    True,
    False
])
def test_bool_truish(x):
    s_type = setting_type('bool')
    assert s_type.validate(x)


@mark.parametrize('x', [
    None,
    1,
    0,
    'True',
])
def test_bool_falsish(x):
    s_type = setting_type('bool')
    assert not s_type.validate(x)


@mark.parametrize('option_kind', ['Flags', 'Enum'])
def test_options_type(option_kind):
    # !!! important, keep the elements in the enum declaration sorted alphabetically
    strings = [
        f'{option_kind}[1,2,3]',
        f'{option_kind}["no","yes"]',
        f'{option_kind}[0.0,1]',
        f'{option_kind}[false,true]',
    ]
    types = [setting_type(s) for s in strings]
    for t, s in zip(types, strings):
        assert str(t) == s
        assert all(other is t or other != t for other in types)


@mark.parametrize('option_kind', ['Flags', 'Enum'])
def test_options_order_invariant(option_kind):
    assert setting_type(f'{option_kind}[1,2]') \
           == setting_type(f'{option_kind} [2, 1]') \
           == setting_type(f'{option_kind}[1.0, 2.0]')


def test_enum():
    s_type = setting_type('Enum[1, 15, "yes", "no", true, 0]')
    assert s_type.validate(0)
    assert s_type.validate(1)
    assert s_type.validate(15)
    assert s_type.validate("yes")
    assert s_type.validate("no")
    assert s_type.validate(True)
    assert s_type.validate(1.0)

    assert not s_type.validate(2)
    assert not s_type.validate(False)


def test_flags():
    s_type = setting_type('Flags[1, 15, "yes", "no", true, 0]')
    assert s_type.validate([0, 1, 15])
    assert s_type.validate([])
    assert s_type.validate(["yes", "no"])
    assert s_type.validate([True, 0])
    assert s_type.validate(["no"])

    assert not s_type.validate([1, 2])
    assert not s_type.validate([False])
    assert not s_type.validate({"yes": True})
    assert not s_type.validate([True, 0, 0])


def test_generic_sequence():
    s_type = setting_type('Sequence<Enum[1,2,3]>')
    assert s_type.validate([1, 3, 1, 2])
    assert s_type.validate([1])
    assert s_type.validate([])

    assert not s_type.validate(1)
    assert not s_type.validate({1: 1})
    assert not s_type.validate([1, 3, 6])


def test_nested_sequence():
    s_type = setting_type('Sequence<Sequence<int>>')
    assert s_type.validate([[3, 2, 1], [8, 7, 6, 5, 4], [15, 14, 13, 12, 11, 10, 9]])

    assert not s_type.validate([3, 2, 1])


def test_generic_mapping():
    s_type = setting_type('Mapping<Enum[1,2,3]>')
    assert s_type.validate({'one': 1, 'three': 3, 'oneagain': 1, 'two': 2})
    assert s_type.validate({'one': 1})
    assert s_type.validate({})

    assert not s_type.validate(1)
    assert not s_type.validate([1])
    assert not s_type.validate({'one': 1, 'three': 3, 'six': 6})


@mark.parametrize('gen_kind', ['Sequence', 'Mapping'])
def test_generic_types(gen_kind):
    strings = [
        f'{gen_kind}<int>',
        f'{gen_kind}<float>',
        f'{gen_kind}<bool>',
        f'{gen_kind}<str>',
        f'{gen_kind}<Enum[false,true]>',
        f'{gen_kind}<Sequence<int>>',
    ]
    types = [setting_type(s) for s in strings]
    for t, s in zip(types, strings):
        assert str(t) == s
        assert all(other is t or other != t for other in types)


@mark.parametrize('setting_type_name', [
    'Sequence<Sequence<int>>',
    'Mapping<str>',
    'str',
    'int',
    'bool',
    'float',
    'Flags["hi", "there"]',
    'Enum[0,1,2,3,4]',
    'Flags[0,1,2,3,4]'
])
@mark.parametrize('input', [
    0, 1, 2, 3, [1, 2, 3], "hi", 15.6, False, True, None, object(), {'hi': 'there'}, [], ('a', 'b', 'c'), ['hi'], [[]]
])
def test_validation_never_fails(setting_type_name, input):
    st = setting_type(setting_type_name)
    assert isinstance(st.validate(input), bool)
