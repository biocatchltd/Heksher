from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union, Any

from fastapi import APIRouter
from pydantic import Json, Field, validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import application, ORJSONModel, router as v1_router
from heksher.app import HeksherApp
from heksher.db_logic.rule import RuleSpec
from heksher.setting import Setting

router = APIRouter(prefix='/rules')


@router.delete('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, app: HeksherApp = application):
    rule_spec = await app.db_logic.get_rule(rule_id)

    if not rule_spec:
        return PlainTextResponse('rule with id not found', status_code=status.HTTP_404_NOT_FOUND)

    await app.db_logic.delete_rule(rule_id)
    await app.db_logic.touch_setting(rule_spec.setting)


class SearchRuleInput(ORJSONModel):
    setting: str
    feature_values: Dict[str, str]

    @validator('feature_values')
    @classmethod
    def feature_values_not_empty(cls, v):
        if not v:
            raise ValueError('feature_value must not be empty')
        return v


class SearchRuleOutput(ORJSONModel):
    rule_id: int


@router.get('/search', response_model=SearchRuleOutput)
async def search_rule(input: SearchRuleInput, app: HeksherApp = application):
    rule_id = await app.db_logic.get_rule_id(input.setting, input.feature_values)
    if not rule_id:
        return PlainTextResponse('rule not found', status_code=status.HTTP_404_NOT_FOUND)
    return SearchRuleOutput(rule_id=rule_id)


class AddRuleInput(ORJSONModel):
    setting: str
    feature_values: Dict[str, str]
    value: Any
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AddRuleOutput(ORJSONModel):
    rule_id: int


@router.post('', response_model=AddRuleOutput, status_code=status.HTTP_201_CREATED)
async def add_rule(input: AddRuleInput, app: HeksherApp = application):
    setting: Optional[Setting] = await app.db_logic.get_setting(input.setting)
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

    existing_rule = await app.db_logic.get_rule_id(input.setting, input.feature_values)
    if existing_rule:
        return PlainTextResponse('rule already exists', status_code=status.HTTP_409_CONFLICT)

    new_id = await app.db_logic.add_rule(input.setting, input.value, input.metadata, input.feature_values)
    await app.db_logic.touch_setting(input.setting)

    return AddRuleOutput(rule_id=new_id)


class QueryRulesInput(ORJSONModel):
    setting_names: List[str]
    context_features_options: Dict[str, List[str]]
    cache_time: Optional[datetime] = None
    include_metadata: bool = False


class Rule(ORJSONModel):
    setting: str
    value: Any
    context_features: List[Tuple[str, str]]


class RuleWithMetadata(Rule):
    metadata: Dict[str, Any]


class QueryRulesOutput(ORJSONModel):
    rule: List[Rule]


class QueryRulesOutputWithMetadata(ORJSONModel):
    rule: List[RuleWithMetadata]


@router.get('/query', response_model=Union[QueryRulesOutput, QueryRulesOutputWithMetadata])
async def query_rules(input: QueryRulesInput, app: HeksherApp = application):
    not_context_features = await app.db_logic.get_not_context_features(input.context_features_options)
    if not_context_features:
        return PlainTextResponse(f'the following are not valid context features: {not_context_features}',
                                 status_code=status.HTTP_404_NOT_FOUND)

    not_settings = await app.db_logic.get_not_settings(input.setting_names)
    if not_settings:
        return PlainTextResponse(f'the following are not setting names: {not_settings}',
                                 status_code=status.HTTP_404_NOT_FOUND)

    rules: List[RuleSpec] = await app.db_logic.query_rules(input.setting_names, input.context_features_options,
                                                           input.cache_time, input.include_metadata)

    if input.include_metadata:
        return QueryRulesOutputWithMetadata(rules=[
            RuleWithMetadata(setting=rule.setting, value=rule.value, context_features=rule.feature_values,
                             metadata=rule.metadata)
            for rule in rules
        ])
    else:
        return QueryRulesOutput(rules=[
            Rule(setting=rule.setting, value=rule.value, context_features=rule.feature_values)
            for rule in rules
        ])


class GetRuleOutput(ORJSONModel):
    setting: str
    value: Any
    feature_values: List[Tuple[str, str]]
    metadata: Dict[str, Any]


@router.get('/{rule_id}', response_model=GetRuleOutput)
async def get_rule(rule_id: int, app: HeksherApp = application):
    rule_spec = await app.db_logic.get_rule(rule_id)

    if not rule_spec:
        return PlainTextResponse('rule with id not found', status_code=status.HTTP_404_NOT_FOUND)

    return GetRuleOutput(setting=rule_spec.setting, value=rule_spec.value,
                         feature_values=rule_spec.feature_values, metadata=rule_spec.metadata)


v1_router.include_router(router)
