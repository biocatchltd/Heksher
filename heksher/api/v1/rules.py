from logging import getLogger
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Query, Response
from pydantic import Field, validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.rules_metadata import router as metadata_router
from heksher.api.v1.util import ORJSONModel, PydanticResponse, application, router as v1_router
from heksher.api.v1.validation import ContextFeatureName, ContextFeatureValue, MetadataKey, SettingName
from heksher.app import HeksherApp
from heksher.db_logic.rule import db_add_rule, db_delete_rule, db_get_rule, db_get_rule_id, db_patch_rule
from heksher.db_logic.setting import db_get_setting

router = APIRouter(prefix='/rules')
logger = getLogger(__name__)


@router.delete('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule(rule_id: int, app: HeksherApp = application):
    """
    Remove a rule.
    """
    async with app.engine.begin() as conn:
        rule_spec = await db_get_rule(conn, rule_id, include_metadata=False)

        if not rule_spec:
            return Response(status_code=status.HTTP_404_NOT_FOUND)

        await db_delete_rule(conn, rule_id)


class SearchRuleOutput(ORJSONModel):
    rule_id: int


@router.get('/search', response_model=SearchRuleOutput)
async def search_rule(app: HeksherApp = application,
                      setting: str = Query(...,
                                           description="the name of the setting to search",
                                           regex='[a-zA-Z_0-9.]+$'),
                      feature_values: str = Query(...,
                                                  description="a comma-separated list of context features for the "
                                                              "rule",
                                                  regex='[a-zA-Z_0-9]+:[a-zA-Z_0-9]+(,[a-zA-Z_0-9]+:[a-zA-Z_0-9]+)*$',
                                                  example=["a:X,c:Z"]), ):
    """
    Get the ID of a rule with specific conditions.
    """
    async with app.engine.connect() as conn:
        canon_setting = await db_get_setting(conn, setting, include_metadata=False, include_configurable_features=False,
                                             include_aliases=False)  # for aliasing
        if not canon_setting:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        feature_values_dict: Dict[str, str] = dict(
            part.split(':') for part in feature_values.split(','))  # type: ignore
        rule_id = await db_get_rule_id(conn, canon_setting.name, feature_values_dict)
        if not rule_id:
            return Response(status_code=status.HTTP_404_NOT_FOUND)
        return SearchRuleOutput(rule_id=rule_id)


class AddRuleInput(ORJSONModel):
    setting: SettingName = Field(description="the setting name the rule should apply to")
    feature_values: Dict[ContextFeatureName, ContextFeatureValue] = \
        Field(description="the exact-match conditions of the rule")
    value: Any = Field(..., description="the value of the setting in contexts that match the rule")
    metadata: Dict[MetadataKey, Any] = Field(default_factory=dict, description="additional metadata of the rule")

    @validator('feature_values')
    @classmethod
    def feature_values_not_empty(cls, v):
        if not v:
            raise ValueError('feature_values must not be empty')
        return v


class AddRuleOutput(ORJSONModel):
    rule_id: int


@router.post('', response_model=AddRuleOutput, status_code=status.HTTP_201_CREATED)
async def add_rule(input: AddRuleInput, app: HeksherApp = application):
    """
    Add a rule, and get its ID.
    """
    async with app.engine.begin() as conn:
        setting = await db_get_setting(conn, input.setting, include_metadata=False, include_configurable_features=True,
                                       include_aliases=False)
        if not setting:
            return PlainTextResponse(f'setting not found with name {input.setting}',
                                     status_code=status.HTTP_422_UNPROCESSABLE_ENTITY)
        not_configurable = input.feature_values.keys() - setting.configurable_features
        if not_configurable:
            return PlainTextResponse(f'setting is not configurable at context features {not_configurable}',
                                     status_code=status.HTTP_400_BAD_REQUEST)

        if not setting.type.validate(input.value):
            return PlainTextResponse(f'rule value is incompatible with setting type {setting.type}',
                                     status_code=status.HTTP_400_BAD_REQUEST)

        existing_rule = await db_get_rule_id(conn, setting.name, input.feature_values)
        if existing_rule:
            return PlainTextResponse('rule already exists', status_code=status.HTTP_409_CONFLICT)

        new_id = await db_add_rule(conn, setting.name, input.value, input.metadata, input.feature_values)

    return PydanticResponse(AddRuleOutput(rule_id=new_id),
                            headers={'Location': f'/{new_id}'}, status_code=status.HTTP_201_CREATED)


class PatchRuleInput(ORJSONModel):
    value: Any = Field(..., description="the value of the setting in contexts that match the rule")


@router.patch('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.put('/{rule_id}/value', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def patch_rule(rule_id: int, input: PatchRuleInput, app: HeksherApp = application):
    """
    Modify existing rule's value
    """
    async with app.engine.begin() as conn:
        rule = await db_get_rule(conn, rule_id, include_metadata=False)
        if not rule:
            return PlainTextResponse(status_code=status.HTTP_404_NOT_FOUND)

        setting = await db_get_setting(conn, rule.setting, include_metadata=False, include_aliases=False,
                                       include_configurable_features=False)
        assert setting

        if not setting.type.validate(input.value):
            return PlainTextResponse(f'rule value is incompatible with setting type {setting.type}',
                                     status_code=status.HTTP_400_BAD_REQUEST)

        await db_patch_rule(conn, rule_id, input.value)


class GetRuleOutput(ORJSONModel):
    setting: str = Field(description="the setting the rule applies to")
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    feature_values: List[Tuple[str, str]] = Field(description="a list of exact-match conditions for the rule")
    metadata: Dict[MetadataKey, Any] = Field(description="the metadata of the rule")


@router.get('/{rule_id}', response_model=GetRuleOutput)
async def get_rule(rule_id: int, app: HeksherApp = application):
    async with app.engine.connect() as conn:
        rule_spec = await db_get_rule(conn, rule_id, include_metadata=True)

        if not rule_spec:
            return Response(status_code=status.HTTP_404_NOT_FOUND)

        return GetRuleOutput(setting=rule_spec.setting, value=rule_spec.value,
                             feature_values=rule_spec.feature_values, metadata=rule_spec.metadata)


router.include_router(metadata_router)
v1_router.include_router(router)
