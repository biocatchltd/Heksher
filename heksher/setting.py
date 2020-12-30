from dataclasses import dataclass
from datetime import datetime
from typing import Optional, FrozenSet, Any, Dict

from heksher.setting_types import SettingType

NOT_LOADED = object()
"""
A sentinel value to place in setting attributes that have not been loaded for efficiency.
"""


@dataclass
class Setting:
    name: str
    type: SettingType
    default_value: Optional[str]
    last_touch_time: datetime
    configurable_features: FrozenSet[str]
    metadata: Dict[str, Any]
