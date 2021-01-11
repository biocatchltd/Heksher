from heksher.util import JsonPrimitiveSet


def test_json_primitive_set():
    s = JsonPrimitiveSet([1, 2.0, False, "hi", 2])
    assert 1 in s
    assert 1.0 in s
    assert 2 in s
    assert 0 not in s
    assert 0.0 not in s
    assert "hi" in s
    assert True not in s
    assert False in s

    assert set(s) == {1, 2.0, False, "hi"}
    assert len(s) == 4


def test_json_primitive_duplicates():
    s = JsonPrimitiveSet([0, False])
    assert 0 in s
    assert 0.0 in s
    assert False in s

    assert set(s) == {0}
    assert len(s) == 2
