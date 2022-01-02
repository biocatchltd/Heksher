from typing import TYPE_CHECKING

from pydantic import constr

if TYPE_CHECKING:
    ContextFeatureName = str
    ContextFeatureValue = str
    SettingName = str
    MetadataKey = str
    SettingVersion = str
else:
    ContextFeatureName = constr(regex='[a-zA-Z_0-9]+$')
    ContextFeatureValue = constr(regex='[a-zA-Z_0-9]+$')
    SettingName = constr(regex='[a-zA-Z_0-9.]+$')
    MetadataKey = constr(regex='[a-zA-Z0-9_-]+$')
    SettingVersion = constr(regex='^[0-9]+\.[0-9]+$')
