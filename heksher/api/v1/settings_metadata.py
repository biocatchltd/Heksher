from logging import getLogger
from typing import Any, Dict, Optional

from fastapi import APIRouter, Response
from pydantic import Field
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, application
from heksher.api.v1.validation import MetadataKey, SettingVersion
from heksher.app import HeksherApp
from heksher.db_logic.setting import db_get_setting
from heksher.db_logic.setting_metadata import (
    db_delete_setting_metadata, db_delete_setting_metadata_key, db_replace_setting_metadata, db_update_setting_metadata,
    db_update_setting_metadata_key
)
from heksher.db_logic.util import parse_setting_version

router = APIRouter()
logger = getLogger(__name__)


class InputSettingMetadata(ORJSONModel):
    metadata: Dict[MetadataKey, Any] = Field(default_factory=dict, description="user-defined metadata of the setting")
    version: SettingVersion = Field(description='the new version to assign to the setting')


@router.post('/{name}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def update_setting_metadata(name: str, input: InputSettingMetadata, app: HeksherApp = application):
    """
    Update the setting's metadata
    """
    async with app.engine.begin() as conn:
        setting = await db_get_setting(conn, name, include_metadata=False, include_aliases=False,
                                       include_configurable_features=False)
        if not setting:
            return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
        existing_version = parse_setting_version(setting.version)
        new_version = parse_setting_version(input.version)
        if existing_version >= new_version:
            return PlainTextResponse(f'The setting {name} already has a newer version ({setting.version})',
                                     status_code=status.HTTP_409_CONFLICT)
        async with app.engine.begin() as conn:
            await db_update_setting_metadata(conn, setting.name, input.metadata, input.version)


@router.put('/{name}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def replace_setting_metadata(name: str, input: InputSettingMetadata, app: HeksherApp = application):
    """
    Change the current metadata of the setting.
    """
    async with app.engine.begin() as conn:
        setting = await db_get_setting(conn, name, include_metadata=False, include_aliases=False,
                                       include_configurable_features=False)
        if not setting:
            return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
        existing_version = parse_setting_version(setting.version)
        new_version = parse_setting_version(input.version)
        if existing_version >= new_version:
            return PlainTextResponse(f'The setting {name} already has a newer version ({setting.version})',
                                     status_code=status.HTTP_409_CONFLICT)
        async with app.engine.begin() as conn:
            await db_replace_setting_metadata(conn, setting.name, input.metadata, input.version)


class PutSettingMetadataKey(ORJSONModel):
    value: Any = Field(..., description="the new value of the given key and setting in the setting's metadata")
    version: SettingVersion = Field(description='the new version to assign to the setting')


@router.put('/{name}/metadata/{key}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def update_setting_metadata_key(name: str, key: MetadataKey, input: PutSettingMetadataKey,
                                      app: HeksherApp = application):
    """
    Updates the current metadata of the setting. Existing keys won't be deleted.
    """
    async with app.engine.begin() as conn:
        setting = await db_get_setting(conn, name, include_metadata=False, include_aliases=False,
                                       include_configurable_features=False)
        if not setting:
            return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
        existing_version = parse_setting_version(setting.version)
        new_version = parse_setting_version(input.version)
        if existing_version >= new_version:
            return PlainTextResponse(f'The setting {name} already has a newer version ({setting.version})',
                                     status_code=status.HTTP_409_CONFLICT)
        async with app.engine.begin() as conn:
            await db_update_setting_metadata_key(conn, setting.name, key, input.value, input.version)


class DeleteSettingMetadataInput(ORJSONModel):
    version: SettingVersion = Field(description='the new version to assign to the setting')


@router.delete('/{name}/metadata', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_setting_metadata(name: str, input: DeleteSettingMetadataInput, app: HeksherApp = application):
    """
    Delete a setting's metadata.
    """
    async with app.engine.begin() as conn:
        setting = await db_get_setting(conn, name, include_metadata=False, include_aliases=False,
                                       include_configurable_features=False)
        if not setting:
            return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
        existing_version = parse_setting_version(setting.version)
        new_version = parse_setting_version(input.version)
        if existing_version >= new_version:
            return PlainTextResponse(f'The setting {name} already has a newer version ({setting.version})',
                                     status_code=status.HTTP_409_CONFLICT)
        async with app.engine.begin() as conn:
            await db_delete_setting_metadata(conn, setting.name, input.version)


@router.delete('/{name}/metadata/{key}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule_key_from_metadata(name: str, key: MetadataKey, input: DeleteSettingMetadataInput,
                                        app: HeksherApp = application):
    """
    Delete a specific key from the setting's metadata.
    """
    async with app.engine.begin() as conn:
        setting = await db_get_setting(conn, name, include_metadata=False, include_aliases=False,
                                       include_configurable_features=False)
        if not setting:
            return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
        existing_version = parse_setting_version(setting.version)
        new_version = parse_setting_version(input.version)
        if existing_version >= new_version:
            return PlainTextResponse(f'The setting {name} already has a newer version ({setting.version})',
                                     status_code=status.HTTP_409_CONFLICT)
        async with app.engine.begin() as conn:
            await db_delete_setting_metadata_key(conn, setting.name, key, input.version)


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
    async with app.engine.begin() as conn:
        if not (setting := await db_get_setting(conn, name, include_metadata=True, include_aliases=False,
                                                include_configurable_features=False)):
            return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    return GetSettingMetadataOutput(metadata=setting.metadata)
