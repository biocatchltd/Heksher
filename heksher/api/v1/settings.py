from datetime import datetime
from logging import getLogger
from typing import List, Dict, Any, Union

import orjson
from fastapi import APIRouter
from pydantic import Field, root_validator  # pytype: disable=import-error
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import application, ORJSONModel, router as v1_router
from heksher.api.v1.validation import SettingName, ContextFeatureName
from heksher.app import HeksherApp
from heksher.setting import Setting
from heksher.setting_types import SettingType

router = APIRouter(prefix='/settings')

logger = getLogger(__name__)


class DeclareSettingInput(ORJSONModel):
    name: SettingName = Field(description="the name of the setting")
    configurable_features: List[ContextFeatureName] = Field(
        description="a list of context features that the setting should allow rules to match by"
    )
    type: SettingType = Field(description="the type of the setting")
    default_value: Any = Field(None, description="the default value of the rule, must be applicable to the setting's"
                                                 " value")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="user-defined metadata of the rule")

    def to_setting(self) -> Setting:
        return Setting(self.name, self.type, self.default_value, self.configurable_features, self.metadata)

    @root_validator(skip_on_failure=True)
    @classmethod
    def default_value_matches(cls, values: Dict[str, Any]):
        default = values['default_value']
        if default is None:
            return values
        type_: SettingType = values['type']
        if not type_.validate(default):
            raise TypeError(f'type ({type_}) and default value ({default}) must match')
        return values


class DeclareSettingOutput(ORJSONModel):
    created: bool = Field(description="whether the fields was newly created by the request")
    changed: List[str] = Field(description="a list of fields that were changed by the request")
    incomplete: Dict[str, Any] = Field(
        description="a mapping of fields that were declared with incomplete data. The values in the mapping represent"
                    " the complete data with (which remains unchanged)"
    )


@router.put('/declare', response_model=DeclareSettingOutput)
async def declare_setting(input: DeclareSettingInput, app: HeksherApp = application):
    """
    Ensure that a setting exists, creating it if necessary.
    """
    new_setting = input.to_setting()
    existing = await app.db_logic.get_setting(input.name)
    if existing is None:
        not_cf = await app.db_logic.get_not_found_context_features(input.configurable_features)
        if not_cf:
            return PlainTextResponse(f'{not_cf} are not acceptable context features',
                                     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
        logger.info('creating new setting', extra={'setting_name': new_setting.name})
        await app.db_logic.add_setting(new_setting)
        return DeclareSettingOutput(created=True, changed=[], incomplete={})

    to_change = {'last_touch_time': datetime.now()}
    changed = []
    incomplete = {}

    existing_setting_cfs = frozenset(existing.configurable_features)
    new_setting_cfs = frozenset(new_setting.configurable_features)

    new_configurable_features = new_setting_cfs - existing_setting_cfs
    if new_configurable_features:
        # we need to make sure the new CFs are actually CFs
        not_cf = await app.db_logic.get_not_found_context_features(new_configurable_features)
        if not_cf:
            return PlainTextResponse(f'{not_cf} are not acceptable context features',
                                     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
        changed.append('configurable_features')
        logger.info("adding new configurable features to setting",
                    extra={'setting_name': new_setting.name, 'new_configurable_features': new_configurable_features})

    missing_cf = existing_setting_cfs - new_setting_cfs
    if missing_cf:
        # note: there is a slight potential mislead here. If a user both declares new CFs and omits existing CFs,
        # the new CFs will not appear in the response. This is fine for now
        incomplete['configurable_features'] = existing.configurable_features

    if existing.type != new_setting.type:
        return PlainTextResponse(
            f'setting already exists with conflicting type. Expected {existing.type}, got {new_setting.type}',
            status_code=status.HTTP_409_CONFLICT
        )

    if existing.default_value != new_setting.default_value:
        to_change['default_value'] = str(orjson.dumps(new_setting.default_value), 'utf-8')
        changed.append('default_value')

    # we need to get which metadata keys are changed
    metadata_changed = existing.metadata.keys() ^ new_setting.metadata.keys()
    metadata_changed.update(
        k for (k, v) in existing.metadata.items() if (k in new_setting.metadata and new_setting.metadata[k] != v)
    )
    if metadata_changed:
        logger.info('changing setting metadata',
                    extra={'setting_name': new_setting.name, 'new_metadata': new_setting.metadata})
        changed.extend('metadata.' + k for k in sorted(metadata_changed))
        to_change['metadata'] = str(orjson.dumps(new_setting.metadata), 'utf-8')

    if to_change or new_configurable_features:
        await app.db_logic.update_setting(input.name, to_change, new_configurable_features)
    return DeclareSettingOutput(created=False, changed=changed, incomplete=incomplete)


@router.delete('/{name}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(name: str, app: HeksherApp = application):
    """
    Delete a setting.
    """
    deleted = await app.db_logic.delete_setting(name)
    if not deleted:
        return PlainTextResponse('setting name not found', status_code=status.HTTP_404_NOT_FOUND)


class GetSettingOutput(ORJSONModel):
    name: str = Field(description="the name of the setting")
    configurable_features: List[str] = Field(description="a list of the context features the setting can be configured"
                                                         " by")
    type: str = Field(description="the type of the setting")
    default_value: Any = Field(description="the default value of the setting")
    metadata: Dict[str, Any] = Field(description="additional metadata of the setting")


@router.get('/{name}', response_model=GetSettingOutput,
            responses={
                status.HTTP_404_NOT_FOUND: {
                    "description": "The setting does not exist.",
                }
            })
async def get_setting(name: str, app: HeksherApp = application):
    """
    Get details on a setting.
    """
    setting = await app.db_logic.get_setting(name)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    return GetSettingOutput(name=setting.name, configurable_features=setting.configurable_features,
                            type=str(setting.type), default_value=setting.default_value, metadata=setting.metadata)


# https://github.com/tiangolo/fastapi/issues/2724
class GetSettingsOutput_Setting(ORJSONModel):
    name: str = Field(description="The name of the setting")


class GetSettingsOutput(ORJSONModel):
    settings: List[GetSettingsOutput_Setting] = Field(description="A list of all the setting, sorted by name")


class GetSettingsOutputWithData_Setting(GetSettingsOutput_Setting):
    configurable_features: List[str] = Field(
        description="a list of the context features the setting can be configured"
                    " by")
    type: str = Field(description="the type of the setting")
    default_value: Any = Field(description="the default value of the setting")
    metadata: Dict[str, Any] = Field(description="additional metadata of the setting")


class GetSettingsOutputWithData(ORJSONModel):
    settings: List[GetSettingsOutputWithData_Setting] = Field(description="A list of all the setting, sorted by name")


@router.get('', response_model=Union[GetSettingsOutputWithData, GetSettingsOutput])
async def get_settings(include_additional_data: bool = False, app: HeksherApp = application):
    """
    List all the settings in the service
    """
    results = await app.db_logic.get_settings(include_additional_data)
    if include_additional_data:
        return GetSettingsOutputWithData(settings=[
            GetSettingsOutputWithData_Setting(
                name=spec.name,
                configurable_features=spec.configurable_features,
                type=spec.raw_type,
                default_value=spec.default_value,
                metadata=spec.metadata
            ) for spec in results
        ])
    else:
        return GetSettingsOutput(settings=[
            GetSettingsOutput_Setting(
                name=spec.name
            ) for spec in results
        ])


v1_router.include_router(router)
