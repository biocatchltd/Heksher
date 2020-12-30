from datetime import datetime
from typing import List, Dict, Any

import orjson
from pydantic import Json, Field, root_validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import router, application, ORJSONModel
from heksher.app import HeksherApp
from heksher.setting import Setting
from heksher.setting_types import SettingType


class DeclareSettingInput(ORJSONModel):
    name: str
    configurable_features: List[str]
    type: SettingType
    default_value: Json = None
    metadata: Dict[str, Json] = Field(default_factory=dict)

    def to_setting(self) -> Setting:
        return Setting(self.name, self.type,
                       str(orjson.dumps(self.default_value), 'utf-8'),
                       datetime.now(), frozenset(self.configurable_features),
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


class DeclareSettingResponse(ORJSONModel):
    created: bool
    rewritten: List[str]


@router.post('/declare_setting', response_model=DeclareSettingResponse)
async def declare_setting(input: DeclareSettingInput, app: HeksherApp = application):
    not_cf = app.db_logic.get_not_context_features(input.configurable_features)
    if not_cf:
        return PlainTextResponse(f'{not_cf} are not acceptable context features',
                                 status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
    new_setting = input.to_setting()
    existing = await app.db_logic.get_setting(input.name)
    if existing is None:
        await app.db_logic.insert_setting(new_setting)
        return DeclareSettingResponse(created=True, rewritten=[])

    changed = {'last_touch_time': datetime.now()}
    rewritten = []

    missing_cf = existing.configurable_features - new_setting.configurable_features
    if missing_cf:
        return PlainTextResponse(f'setting already exists with missing configurable features {missing_cf}',
                                 status_code=status.HTTP_409_CONFLICT)

    new_configurable_features = new_setting.configurable_features - existing.configurable_features
    if new_configurable_features:
        rewritten.append('configurable_features')

    if existing.type != new_setting.type:
        return PlainTextResponse(
            f'setting already exists with conflicting type. Expected {existing.type}, got {new_setting.type}',
            status_code=status.HTTP_409_CONFLICT
        )

    if existing.default_value != new_setting.default_value:
        changed['default_value'] = new_setting.default_value
        rewritten.append('default_value')

    # we need to get which metadata keys are changed
    metadata_changed = existing.metadata.keys() ^ new_setting.metadata.keys()
    metadata_changed.update(
        k for (k, v) in existing.metadata.items() if (k in new_setting.metadata and new_setting.metadata[k] != v)
    )
    if metadata_changed:
        rewritten.extend('metadata.'+k for k in metadata_changed)
        changed['metadata'] = str(orjson.dumps(new_setting.metadata), 'utf-8')

    await app.db_logic.update_setting(input.name, changed)
    return DeclareSettingResponse(created=False, rewritten=rewritten)
