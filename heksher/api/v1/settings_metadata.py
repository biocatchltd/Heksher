from logging import getLogger
from typing import Any, Dict, Optional

from fastapi import APIRouter, Response
from pydantic import Field
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, application
from heksher.api.v1.validation import MetadataKey
from heksher.app import HeksherApp

router = APIRouter()
logger = getLogger(__name__)


class InputSettingMetadata(ORJSONModel):
    metadata: Dict[MetadataKey, Any] = Field(default_factory=dict, description="user-defined metadata of the setting")


@router.post('/{name}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def update_setting_metadata(name: str, input: InputSettingMetadata, app: HeksherApp = application):
    """
    Update the setting's metadata
    """
    if not input.metadata:
        return None
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.update_setting_metadata(setting.name, input.metadata)


@router.put('/{name}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def replace_setting_metadata(name: str, input: InputSettingMetadata, app: HeksherApp = application):
    """
    Change the current metadata of the setting.
    """
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    if not input.metadata:
        # empty dictionary equals to deleting the metadata
        await app.db_logic.delete_setting_metadata(setting.name)
    else:
        await app.db_logic.replace_setting_metadata(setting.name, input.metadata)


class PutSettingMetadataKey(ORJSONModel):
    value: Any = Field(description="the new value of the given key and setting in the setting's metadata")


@router.put('/{name}/metadata/{key}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def update_setting_metadata_key(name: str, key: MetadataKey, input: PutSettingMetadataKey,
                                      app: HeksherApp = application):
    """
    Updates the current metadata of the setting. Existing keys won't be deleted.
    """
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.update_setting_metadata_key(setting.name, key, input.value)


@router.delete('/{name}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_setting_metadata(name: str, app: HeksherApp = application):
    """
    Delete a setting's metadata.
    """
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.delete_setting_metadata(setting.name)


@router.delete('/{name}/metadata/{key}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule_key_from_metadata(name: str, key: MetadataKey, app: HeksherApp = application):
    """
    Delete a specific key from the setting's metadata.
    """
    setting = await app.db_logic.get_setting(name, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    await app.db_logic.delete_setting_metadata_key(setting.name, key)


class GetSettingMetadataOutput(ORJSONModel):
    metadata: Optional[Dict[MetadataKey, Any]] = Field(default_factory=dict,
                                                       description="user-defined metadata of the setting")


@router.get('/{name}/metadata', response_model=GetSettingMetadataOutput,
            responses={
                status.HTTP_404_NOT_FOUND: {
                    "description": "The setting does not exist.",
                }
            })
async def get_setting_metadata(name: str, app: HeksherApp = application):
    """
    Get metadata of a setting.
    """
    if not (setting := await app.db_logic.get_setting(name, include_metadata=True, include_aliases=False,
                                                      include_configurable_features=False)):
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    return GetSettingMetadataOutput(metadata=setting.metadata)
