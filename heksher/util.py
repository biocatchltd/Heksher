from typing import AbstractSet, Union, Any, Tuple, Set


class JsonPrimitiveSet(AbstractSet[Union[str, bool, float, int]]):
    def __init__(self, elements):
        self._inner: Set[Tuple[type, Any]] = set(self._inner_element(e) for e in elements)

    @classmethod
    def _inner_element(cls, v):
        if type(v) is int:
            return float, v
        if type(v) not in (float, str, bool):
            raise TypeError(f'expected a primitive type, got {type(v)}')
        return type(v), v

    def __contains__(self, item):
        return self._inner_element(item) in self._inner

    def __iter__(self):
        return (yield from (i[1] for i in self._inner))

    def __len__(self):
        return len(self._inner)
