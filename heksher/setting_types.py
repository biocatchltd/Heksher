from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import AbstractSet, Pattern, Sequence, Tuple, Type

from orjson import loads

from heksher.util import JsonPrimitiveSet


class SettingType(ABC):
    """An abstract setting type base class"""
    @abstractmethod
    def validate(self, x) -> bool:
        """
        Args:
            x: an arbitrary, JSON parsed value

        Returns:
            Whether x is a valid element of the the type self

        """
        pass

    @abstractmethod
    def __str__(self):
        """
        A string representation of self
        Notes:
            The following should uphold to all setting types:
            ```
            setting_type(str(self)) == self
            ```
            However, the inverse is not necessarily true
            ```
            str(setting_type("Enum[3,2,1]")) != "Enum[3,2,1]"
            ```
        """
        pass

    @abstractmethod
    def __eq__(self, other):
        pass

    @abstractmethod
    def __lt__(self, other: SettingType):
        pass

    @abstractmethod
    def __gt__(self, other: SettingType):
        """
        Type a >= type b if every element of b is also a member of a.
        Args:
            other: The compared setting type
        Returns:
            Whether or not the current setting type > the other setting type
        """
        pass

    def __le__(self, other):
        return self < other or self == other

    def __ge__(self, other):
        return self > other or self == other

    # methods to allow the class to be used as a pydantic field
    @classmethod
    def __get_validators__(cls):
        def validator(v):
            if not isinstance(v, str):
                raise ValueError(f'expected string, got {type(v).__name__}')
            return setting_type(v)

        yield validator

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            title='Setting Type',
            type='string',
            example=['int', 'str', 'float', 'bool', 'Enum["blue", "green", "red"]', 'Sequence<Mapping<str>>'],
        )


class PrimitiveSettingType(SettingType):
    """
    A setting type for all primitive JSON types (float, str, bool)
    """
    def __init__(self, types: Tuple[type, ...]):
        """
        Args:
            types: The python types that correlate with the JSON types (note that a value must match the class exactly)
        """
        self.types = types

    def __eq__(self, other):
        if isinstance(other, PrimitiveSettingType):
            return self.types == other.types
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, PrimitiveSettingType):
            return set(self.types) < set(other.types)
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, PrimitiveSettingType):
            return set(self.types) > set(other.types)
        return NotImplemented

    def __str__(self):
        return self.types[0].__name__

    def validate(self, x) -> bool:
        return type(x) in self.types


class IntegerPrimitiveSettingType(PrimitiveSettingType):
    """
    A setting type for numbers that also requires that the value be whole
    """
    def __init__(self, name: str):
        """
        Args:
            name: The name of the setting type
        """
        super().__init__((int, float))

    def __eq__(self, other):
        if isinstance(other, IntegerPrimitiveSettingType):
            return self.types == other.types
        return NotImplemented

    def __lt__(self, other):
        if type(other) == PrimitiveSettingType:
            # since we impose additional requirements over int values, true primitives are lt only if we encompass their
            # type.
            return set(self.types) <= set(other.types)
        return super().__lt__(other)

    def __gt__(self, other):
        if type(other) == PrimitiveSettingType:
            # since we impose additional requirements over int values, we are never greater then true primitives.
            return False
        return super().__gt__(other)

    def __str__(self):
        return 'int'

    def validate(self, x) -> bool:
        return super().validate(x) and x % 1 == 0


class OptionedSettingType(SettingType, ABC):
    """
    A base class for setting types parameterized by a set of json primitives
    """
    def __init__(self, options: AbstractSet):
        """
        Args:
            options: The options for the type
        """
        self.options = options

    @classmethod
    def from_json_list(cls, json_option_list: str):
        """
        Args:
            json_option_list: a string denoting a json list of primitives

        Returns:
            An instance of cls with options as a JsonPrimitiveSet of the parsed list

        """
        options = loads(json_option_list)
        if not isinstance(options, list):
            raise TypeError(f'expected list, got {type(options)}')
        option_set = JsonPrimitiveSet(options)
        return cls(option_set)


class FlagSettingType(OptionedSettingType):
    """
    An option setting type that accepts all lists that are subsets of the options set
    """
    def __eq__(self, other):
        if isinstance(other, FlagSettingType):
            return self.options == other.options
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, PrimitiveSettingType):
            return False
        if isinstance(other, FlagSettingType):
            return self.options < other.options
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, PrimitiveSettingType):
            return False
        if isinstance(other, FlagSettingType):
            return self.options > other.options
        return NotImplemented

    def __str__(self):
        return 'Flags[' + ",".join(sorted(json.dumps(option) for option in self.options)) + ']'

    def validate(self, x) -> bool:
        if not isinstance(x, list):
            return False
        seen = set()
        for i in x:
            try:
                if i in seen:
                    return False
            except TypeError:  # i is unhashable
                return False
            seen.add(i)
            if i not in self.options:
                return False
        return True


class EnumSettingType(OptionedSettingType):
    """
    An option setting type that accepts all lists that are members of the options set
    """
    def __eq__(self, other):
        if isinstance(other, EnumSettingType):
            return self.options == other.options
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, (PrimitiveSettingType, FlagSettingType)):
            return False
        if isinstance(other, EnumSettingType):
            return self.options < other.options
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, (PrimitiveSettingType, FlagSettingType)):
            return False
        if isinstance(other, EnumSettingType):
            return self.options > other.options
        return NotImplemented

    def __str__(self):
        return 'Enum[' + ",".join(sorted(json.dumps(option) for option in self.options)) + ']'

    def validate(self, x: str) -> bool:
        return x in self.options


class SingleGenericSettingType(SettingType, ABC):
    """
    A base class of setting types that have a single inner setting type as a parameter
    """
    def __init__(self, inner_type: SettingType):
        self.inner_type = inner_type

    @classmethod
    def from_generic_param_name(cls, generic_param_name: str):
        """
        utility method to parse inner parameter
        """
        return cls(setting_type(generic_param_name))


class SequenceSettingType(SingleGenericSettingType):
    """
    A generic setting type that accepts only lists of elements conforming to the inner type
    """
    def __eq__(self, other):
        if isinstance(other, SequenceSettingType):
            return self.inner_type == other.inner_type
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, (PrimitiveSettingType, EnumSettingType, FlagSettingType)):
            return False
        if isinstance(other, SequenceSettingType):
            return self.inner_type < other.inner_type
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, (PrimitiveSettingType, EnumSettingType, FlagSettingType)):
            return False
        if isinstance(other, SequenceSettingType):
            return self.inner_type > other.inner_type
        return NotImplemented

    def __str__(self):
        return f'Sequence<{self.inner_type}>'

    def validate(self, x) -> bool:
        if not isinstance(x, list):
            return False
        return all(self.inner_type.validate(i) for i in x)


class MappingSettingType(SingleGenericSettingType):
    """
    A generic setting type that accepts only dicts of strings to elements conforming to the inner type
    """
    def __eq__(self, other):
        if isinstance(other, MappingSettingType):
            return self.inner_type == other.inner_type
        return NotImplemented

    def __lt__(self, other):
        if isinstance(other, (PrimitiveSettingType, EnumSettingType, FlagSettingType, SequenceSettingType)):
            return False
        if isinstance(other, MappingSettingType):
            return self.inner_type < other.inner_type
        return NotImplemented

    def __gt__(self, other):
        if isinstance(other, (PrimitiveSettingType, EnumSettingType, FlagSettingType, SequenceSettingType)):
            return False
        if isinstance(other, MappingSettingType):
            return self.inner_type > other.inner_type
        return NotImplemented

    def __str__(self):
        return f'Mapping<{self.inner_type}>'

    def validate(self, x) -> bool:
        if not isinstance(x, dict):
            return False
        return all(self.inner_type.validate(i) for i in x.values())


_primitives = {
    'int': IntegerPrimitiveSettingType('int'),
    'float': PrimitiveSettingType((float, int)),
    'str': PrimitiveSettingType((str,)),
    'bool': PrimitiveSettingType((bool,))
}  # a list of all the primitive setting types

_with_options: Sequence[Tuple[Pattern[str], Type[OptionedSettingType]]] = [
    (re.compile(r'Flags\s*'), FlagSettingType),
    (re.compile(r'Enum\s*'), EnumSettingType),
]  # a list of patterns for the option setting types

_generics: Sequence[Tuple[Pattern[str], Type[SingleGenericSettingType]]] = [
    (re.compile(r'Sequence\s*<(?P<param>.*)>$'), SequenceSettingType),
    (re.compile(r'Mapping\s*<(?P<param>.*)>$'), MappingSettingType),
]  # a list of patterns for generic setting types


def setting_type(name: str) -> SettingType:
    """
    Parse a setting type from a string
    Args:
        name: the name of the setting type

    Returns:
        A SettingType represented by the string

    Raises:
        ValueError if the parsing fails

    """
    primitive = _primitives.get(name)
    if primitive:
        return primitive
    for (optioned_pattern, optioned_factory) in _with_options:
        if match := optioned_pattern.match(name):
            return optioned_factory.from_json_list(name[match.end():])
    for (generic_pattern, generic_factory) in _generics:
        if match := generic_pattern.match(name):
            return generic_factory.from_generic_param_name(match.group("param").strip())

    raise ValueError(f'cannot resolve setting type {name}')
