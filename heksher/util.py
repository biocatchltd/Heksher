from typing import AbstractSet, Any, Set, Tuple, Union

from sqlalchemy.engine import URL, make_url


def db_url_with_async_driver(url: str) -> str:
    url_obj: URL = make_url(url)
    full_driver_name = url_obj.drivername
    if full_driver_name != 'postgresql':
        raise ValueError('url must be to a postgresql db and must not include a driver')
    url_obj = url_obj.set(drivername=full_driver_name + '+asyncpg')
    return url_obj.render_as_string(hide_password=False)


class JsonPrimitiveSet(AbstractSet[Union[str, bool, float, int]]):
    """
    A set of primitives that keeps to JS logic instead of python logic, namely:
    * ints and floats are indistinguishable (1 === 1.0)
    * ints and bools are distinguishable (1 !== true)
    """
    # implementation is fairly simple: keep an inner set of elements and tag each member with its type, while ensuring
    # ints and floats are mapped to the same type
    def __init__(self, elements):
        self._inner: Set[Tuple[type, Any]] = set(self._inner_element(e) for e in elements)

    @classmethod
    def _inner_element(cls, v):
        if type(v) is int:
            # ints need to behave like floats
            return float, v
        if type(v) not in (float, str, bool):
            raise TypeError(f'expected a primitive type, got {type(v)}')
        return type(v), v

    def __contains__(self, item):
        try:
            inner_element = self._inner_element(item)
        except TypeError:
            # not a primitive, therefore never will be in the set
            return False
        return inner_element in self._inner

    def __iter__(self):
        return (yield from (i[1] for i in self._inner))

    def __len__(self):
        return len(self._inner)
