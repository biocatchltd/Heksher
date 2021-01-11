from datetime import datetime
from typing import List, Dict, Any

import orjson
from fastapi import APIRouter
from pydantic import Field, root_validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import application, ORJSONModel, router as v1_router
from heksher.app import HeksherApp
from heksher.setting import Setting
from heksher.setting_types import SettingType

router = APIRouter(prefix='/settings')


class DeclareSettingInput(ORJSONModel):
    name: str
    configurable_features: List[str]
    type: SettingType
    default_value: Any = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_setting(self) -> Setting:
        return Setting(self.name, self.type,
                       self.default_value, datetime.now(), frozenset(self.configurable_features),
                       self.metadata)

    @root_validator
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
    created: bool
    rewritten: List[str]


@router.put('/declare', response_model=DeclareSettingOutput)
async def declare_setting(input: DeclareSettingInput, app: HeksherApp = application):
    not_cf = await app.db_logic.get_not_context_features(input.configurable_features)
    if not_cf:
        return PlainTextResponse(f'{not_cf} are not acceptable context features',
                                 status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    new_setting = input.to_setting()
    existing = await app.db_logic.get_setting(input.name)
    if existing is None:
        await app.db_logic.insert_setting(new_setting)
        return DeclareSettingOutput(created=True, rewritten=[])

    changed = {'last_touch_time': datetime.now()}
    rewritten = []

    if existing.configurable_features != new_setting.configurable_features:
        # shortcut since checking for configurable changes is more expensive than we'd like
        missing_cf = \
            [e for e in existing.configurable_features if e not in new_setting.configurable_features]
        if missing_cf:
            return PlainTextResponse(f'setting already exists with missing configurable features {missing_cf}',
                                     status_code=status.HTTP_409_CONFLICT)

        new_configurable_features = \
            [n for n in new_setting.configurable_features if n not in existing.configurable_features]
        if new_configurable_features:
            rewritten.append('configurable_features')

    if existing.type != new_setting.type:
        return PlainTextResponse(
            f'setting already exists with conflicting type. Expected {existing.type}, got {new_setting.type}',
            status_code=status.HTTP_409_CONFLICT
        )

    if existing.default_value != new_setting.default_value:
        changed['default_value'] = str(orjson.dumps(new_setting.default_value), 'utf-8')
        rewritten.append('default_value')

    # we need to get which metadata keys are changed
    metadata_changed = existing.metadata.keys() ^ new_setting.metadata.keys()
    metadata_changed.update(
        k for (k, v) in existing.metadata.items() if (k in new_setting.metadata and new_setting.metadata[k] != v)
    )
    if metadata_changed:
        rewritten.extend('metadata.' + k for k in sorted(metadata_changed))
        changed['metadata'] = str(orjson.dumps(new_setting.metadata), 'utf-8')

    if rewritten:
        app.logger.warn('setting fields changed', extra={'setting': input.name, 'rewritten': rewritten})

    if changed or new_configurable_features:
        await app.db_logic.update_setting(input.name, changed, new_configurable_features)
    return DeclareSettingOutput(created=False, rewritten=rewritten)


@router.delete('/{name}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_setting(name: str, app: HeksherApp = application):
    deleted = await app.db_logic.delete_setting(name)
    if not deleted:
        return PlainTextResponse('setting name not found', status_code=status.HTTP_404_NOT_FOUND)


class GetSettingOutput(ORJSONModel):
    name: str
    configurable_features: List[str]
    type: str
    default_value: Any
    metadata: Dict[str, Any]


@router.get('/{name}', response_model=GetSettingOutput,
            responses={
                status.HTTP_404_NOT_FOUND: {
                    "description": "The setting does not exist.",
                }
            })
async def get_setting(name: str, app: HeksherApp = application):
    setting = await app.db_logic.get_setting(name)
    if not setting:
        return PlainTextResponse(f'the setting {name} does not exist', status_code=status.HTTP_404_NOT_FOUND)
    return GetSettingOutput(name=setting.name, configurable_features=setting.configurable_features,
                            type=str(setting.type), default_value=setting.default_value, metadata=setting.metadata)


class GetSettingsOutput(ORJSONModel):
    settings: List[str]


@router.get('', response_model=GetSettingsOutput)
async def get_settings(app: HeksherApp = application):
    return GetSettingsOutput(settings=sorted(await app.db_logic.get_settings()))


v1_router.include_router(router)
