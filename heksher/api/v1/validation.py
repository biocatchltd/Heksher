from pydantic import constr  # pytype: disable=import-error

ContextFeatureName = constr(regex='[a-zA-Z_0-9]+$')
ContextFeatureValue = constr(regex='[a-zA-Z_0-9]+$')
SettingName = constr(regex='[a-zA-Z_0-9]+$')
