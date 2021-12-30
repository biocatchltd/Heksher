from logging import getLogger
from typing import Any, Dict, List, Union

from fastapi import APIRouter, Response
from pydantic import Field
from starlette import status
from starlette.responses import JSONResponse, PlainTextResponse

from heksher.api.v1.setting_declaration import declare_setting_endpoint, declare_setting_enpoint_args
from heksher.api.v1.settings_metadata import router as metadata_router
from heksher.api.v1.util import ORJSONModel, application, router as v1_router
from heksher.api.v1.validation import MetadataKey, SettingName
from heksher.app import HeksherApp
from heksher.setting_types import SettingType

router = APIRouter(prefix='/settings')

logger = getLogger(__name__)


router.add_api_route('/declare', declare_setting_endpoint, **declare_setting_enpoint_args)


@router.delete('/{name}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_setting(name: str, app: HeksherApp = application):
    """
    Delete a setting.
    """
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)  # for aliasing
    if not setting:
        return PlainTextResponse('setting name not found', status_code=status.HTTP_404_NOT_FOUND)
    deleted = await app.db_logic.delete_setting(setting.name)
    if not deleted:
        return PlainTextResponse('setting name not found', status_code=status.HTTP_404_NOT_FOUND)


class GetSettingOutput(ORJSONModel):
    name: str = Field(description="the name of the setting")
    configurable_features: List[str] = Field(description="a list of the context features the setting can be configured"
                                                         " by")
    type: str = Field(description="the type of the setting")
    default_value: Any = Field(description="the default value of the setting")
    metadata: Dict[MetadataKey, Any] = Field(description="additional metadata of the setting")
    aliases: List[str] = Field(description="aliases for the setting's name")


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
    setting = await app.db_logic.get_setting(name, include_metadata=True, include_aliases=True,
                                             include_configurable_features=True)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    return GetSettingOutput(name=setting.name, configurable_features=setting.configurable_features,
                            type=setting.raw_type, default_value=setting.default_value, metadata=setting.metadata,
                            aliases=setting.aliases)


# https://github.com/tiangolo/fastapi/issues/2724
class GetSettingsOutput_Setting(ORJSONModel):
    name: str = Field(description="The name of the setting")


class GetSettingsOutput(ORJSONModel):
    settings: List[GetSettingsOutput_Setting] = Field(description="A list of all the setting, sorted by name")


class GetSettingsOutputWithData_Setting(GetSettingsOutput_Setting):
    configurable_features: List[str] = Field(
        description="a list of the context features the setting can be configured by"
    )
    type: str = Field(description="the type of the setting")
    default_value: Any = Field(description="the default value of the setting")
    metadata: Dict[MetadataKey, Any] = Field(description="additional metadata of the setting")
    aliases: List[SettingName] = Field(description="aliases for the setting's name")


class GetSettingsOutputWithData(ORJSONModel):
    settings: List[GetSettingsOutputWithData_Setting] = Field(description="A list of all the setting, sorted by name")


@router.get('', response_model=Union[GetSettingsOutputWithData, GetSettingsOutput])  # type: ignore
async def get_settings(include_additional_data: bool = False, app: HeksherApp = application):
    """
    List all the settings in the service
    """
    if include_additional_data:
        full_results = await app.db_logic.get_all_settings_full()
        return GetSettingsOutputWithData(settings=[
            GetSettingsOutputWithData_Setting(
                name=spec.name,
                configurable_features=spec.configurable_features,
                type=spec.raw_type,
                default_value=spec.default_value,
                metadata=spec.metadata,
                aliases=spec.aliases,
            ) for spec in full_results
        ])
    else:
        results = await app.db_logic.get_all_settings_names()
        return GetSettingsOutput(settings=[
            GetSettingsOutput_Setting(
                name=name
            ) for name in results
        ])


class PutSettingTypeInput(ORJSONModel):
    type: SettingType = Field(description='the new setting type to set')


class PutSettingTypeConflictOutput(ORJSONModel):
    conflicts: List[str] = Field(description='a list of conflicts to changing the rule value')


@router.put('/{name}/type', status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
            responses={
                status.HTTP_409_CONFLICT: {
                    "description": "The new type is incompatible with a rule of the setting, or with the setting's "
                                   "default value.",
                    "model": PutSettingTypeConflictOutput
                }
            }
            )
async def set_setting_type(name: str, input: PutSettingTypeInput, app: HeksherApp = application):
    """
    Change The type of a setting
    """
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    conflicts = []
    new_type = input.type
    if new_type == setting.type:
        return None
    if not new_type.validate(setting.default_value):
        conflicts.append(f'the default value {setting.default_value!r} does not match the new type')
    rules = await app.db_logic.get_rules_for_setting(setting.name)
    bad_rules = {rule_id: rule_value for (rule_id, rule_value) in rules if not new_type.validate(rule_value)}
    if bad_rules:
        conditions = await app.db_logic.get_rules_feature_values(list(bad_rules.keys()))
        for rule_id, value in bad_rules.items():
            conflicts.append(f'rule {rule_id} ({conditions[rule_id]}) has incompatible value {value}')
    if conflicts:
        return JSONResponse(PutSettingTypeConflictOutput(conflicts=conflicts).dict(),
                            status_code=status.HTTP_409_CONFLICT)
    await app.db_logic.set_setting_type(setting.name, new_type)
    return None


class RenameSettingInput(ORJSONModel):
    name: SettingName = Field(description="the new name for the setting")


@router.put('/{name}/name', status_code=status.HTTP_204_NO_CONTENT, response_class=Response,
            responses={
                status.HTTP_404_NOT_FOUND: {
                    "description": "The setting does not exist."
                },
                status.HTTP_409_CONFLICT: {
                    "description": "The new name already exists as another setting's name or alias."
                }
            })
async def rename_setting(name: str, input: RenameSettingInput, app: HeksherApp = application):
    """
    Rename a setting, adding the previous name as an alias
    """
    # we try and validate the names we were given, and check they do not conflict with other settings
    names_map = await app.db_logic.get_canonical_names((name, input.name))
    # the names map should contain 2 entries:
    # the first entry: given original name/alias -> canonical name
    # (could be the same if the given original name is the canonical one)
    canonical_name = names_map[name]
    # if the canonical name is None - this setting does not exist
    if not canonical_name:
        return PlainTextResponse('setting does not exist', status_code=status.HTTP_404_NOT_FOUND)
    # we check that the names differ, otherwise nothing should be done
    if input.name == canonical_name:
        return None
    # the second entry: given new name -> None
    # if the value is not None - this name/alias already exists
    if names_map[input.name] is not None:
        # if this new name is an alias for the same setting,
        # we can allow this operation to make the alias the canonical name
        # otherwise - the operation cannot be done since the new name already exists as another setting's name or alias
        if names_map[input.name] != canonical_name:
            return PlainTextResponse('name already exists', status_code=status.HTTP_409_CONFLICT)

    await app.db_logic.rename_setting(canonical_name, input.name)
    return None


router.include_router(metadata_router)
v1_router.include_router(router)
