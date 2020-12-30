from datetime import datetime
from typing import List, Dict, Any

import orjson
from pydantic import Json, Field, root_validator, validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import router, application, ORJSONModel
from heksher.app import HeksherApp
from heksher.setting import Setting
from heksher.setting_types import SettingType


class DeleteRuleInput(ORJSONModel):
    setting: str
    feature_values: Dict[str, str]

    @validator('feature_values')
    @classmethod
    def feature_values_not_empty(cls, v):
        if not v:
            raise ValueError('feature_value must not be empty')
        return v


@router.delete('/rule')
async def delete_rule(input: DeleteRuleInput, app: HeksherApp = application):
    rule_id = app.db_logic.get_rule_id(input.setting, input.feature_values)
    if not rule_id:
        return PlainTextResponse('rule not found', status_code=status.HTTP_404_NOT_FOUND)

    await app.db_logic.remove_rule(rule_id)
    await app.db_logic.touch_setting(input.setting)
