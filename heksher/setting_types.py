import json
import re
from abc import ABC, abstractmethod
from orjson import loads
from typing import Tuple, FrozenSet, Sequence, Pattern, Type


class SettingType(ABC):
    @abstractmethod
    def validate(self, x) -> bool:
        pass

    @abstractmethod
    def __str__(self):
        pass

    @abstractmethod
    def __eq__(self, other):
        pass

    # methods to allow class to be used as pydantic field
    @classmethod
    def __get_validators__(cls):
        def validator(v):
            if not isinstance(v, str):
                raise TypeError(f'expected string, got {type(v).__name__}')
            return setting_type(v)

        yield validator

    @classmethod
    def __modify_schema__(cls, field_schema):
        field_schema.update(
            examples=['int', 'str', 'float', 'bool', 'Enum["blue", "green", "red"]', 'Sequence<Mapping<str>>'],
        )


class PrimitiveSettingType(SettingType):
    def __init__(self, types: Tuple[type, ...]):
        self.types = types

    def __eq__(self, other):
        return type(self) is type(other) and self.types == other.types

    def __str__(self):
        return self.types[0].__name__

    def validate(self, x) -> bool:
        return type(x) in self.types


class OptionedSettingType(SettingType, ABC):
    def __init__(self, options: FrozenSet):
        self.options = options

    def __eq__(self, other):
        return type(self) is type(other) and self.options == other.options

    @classmethod
    def from_json_list(cls, json_option_list: str):
        options = loads(json_option_list)
        if not isinstance(options, list):
            raise TypeError(f'expected list, got {type(options)}')
        if not all(
                type(option) not in (int, str, float, bool) for option in options
        ):
            raise TypeError('cannot have an option of non-primitive value')
        return cls(frozenset(options))


class FlagSettingType(OptionedSettingType):
    def __str__(self):
        return 'Flags[' + ",".join(json.dumps(option) for option in self.options) + ']'

    def validate(self, x) -> bool:
        seen = set()
        for i in x:
            if i in seen:
                return False
            seen.add(i)
            if i not in self.options:
                return False
        return True


class EnumSettingType(OptionedSettingType):
    def __str__(self):
        return 'Enum[' + ",".join(json.dumps(option) for option in self.options) + ']'

    def validate(self, x: str) -> bool:
        return x in self.options


class SingleGenericSettingType(SettingType, ABC):
    def __init__(self, inner_type: SettingType):
        self.inner_type = inner_type

    def __eq__(self, other):
        return type(self) is type(other) and self.inner_type == other.inner_type

    @classmethod
    def from_generic_param_name(cls, generic_param_name: str):
        return cls(setting_type(generic_param_name))


class SequenceSettingType(SingleGenericSettingType):
    def __str__(self):
        return f'Sequence<{self.inner_type}>'

    def validate(self, x) -> bool:
        if not isinstance(x, list):
            return False
        return all(self.inner_type.validate(i) for i in x)


class MappingSettingType(SingleGenericSettingType):
    def __str__(self):
        return f'Mapping<{self.inner_type}>'

    def validate(self, x) -> bool:
        if not isinstance(x, dict):
            return False
        return all(self.inner_type.validate(i) for i in x.values())


_primitives = {
    'int': PrimitiveSettingType((int,)),
    'float': PrimitiveSettingType((float, int)),
    'str': PrimitiveSettingType((str,)),
    'bool': PrimitiveSettingType((bool,))
}

_with_options: Sequence[Tuple[Pattern[str], Type[OptionedSettingType]]] = [
    (re.compile(r'Flags\s*'), FlagSettingType),
    (re.compile(r'Enums\s*'), EnumSettingType),
]

_generics: Sequence[Tuple[Pattern[str], Type[SingleGenericSettingType]]] = [
    (re.compile(r'Sequence\s*<\s*(?P<param>.*)\s*>$'), SequenceSettingType),
    (re.compile(r'Mapping\s*<\s*(?P<param>.*)\s*>$'), MappingSettingType),
]


def setting_type(name: str) -> SettingType:
    primitive = _primitives.get(name)
    if primitive:
        return primitive
    for (optioned_pattern, factory) in _with_options:
        if match := optioned_pattern.match(name):
            return factory.from_json_list(name[match.end():])
    for (generic_pattern, factory) in _generics:
        if match := generic_pattern.match(name):
            return factory.from_generic_param_name(match.group("param"))

    raise ValueError(f'cannot resolve setting type {name}')
