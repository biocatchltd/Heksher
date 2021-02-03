from dataclasses import dataclass
from typing import Any, Dict, Sequence

from heksher.setting_types import SettingType


@dataclass
class Setting:
    name: str
    """The name of a setting"""
    type: SettingType
    """The type of the setting"""
    default_value: Any
    """The default value of the setting, or None if there is no default value"""
    configurable_features: Sequence[str]
    """The configurable features of the setting, should be in hierarchical order"""
    metadata: Dict[str, Any]
    """user-defined metadata"""
