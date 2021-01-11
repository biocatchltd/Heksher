from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Any, Dict, Collection

from heksher.setting_types import SettingType

NOT_LOADED = object()
"""
A sentinel value to place in setting attributes that have not been loaded for efficiency.
"""


@dataclass
class Setting:
    name: str
    type: SettingType
    default_value: Any
    last_touch_time: datetime
    configurable_features: Collection[str]
    metadata: Dict[str, Any]
