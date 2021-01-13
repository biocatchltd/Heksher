from datetime import datetime
from typing import List, Dict, Optional, Tuple, Union, Any

from fastapi import APIRouter
from pydantic import Field, validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import application, ORJSONModel, router as v1_router
from heksher.app import HeksherApp
from heksher.setting import Setting

router = APIRouter(prefix='/rules')


@router.delete('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_rule(rule_id: int, app: HeksherApp = application):
    """
    remove a rule
    """
    rule_spec = await app.db_logic.get_rule(rule_id)

    if not rule_spec:
        return PlainTextResponse('rule with id not found', status_code=status.HTTP_404_NOT_FOUND)

    await app.db_logic.delete_rule(rule_id)
    await app.db_logic.touch_setting(rule_spec.setting)


class SearchRuleInput(ORJSONModel):
    setting: str = Field(description="the setting name the rule belongs to")
    feature_values: Dict[str, str] = Field(description="the exact-match conditions of the rule")

    @validator('feature_values')
    @classmethod
    def feature_values_not_empty(cls, v):
        if not v:
            raise ValueError('feature_values must not be empty')
        return v


class SearchRuleOutput(ORJSONModel):
    rule_id: int


@router.get('/search', response_model=SearchRuleOutput)
async def search_rule(input: SearchRuleInput, app: HeksherApp = application):
    """
    get the ID of a rule with specific conditions
    """
    rule_id = await app.db_logic.get_rule_id(input.setting, input.feature_values)
    if not rule_id:
        return PlainTextResponse('rule not found', status_code=status.HTTP_404_NOT_FOUND)
    return SearchRuleOutput(rule_id=rule_id)


class AddRuleInput(ORJSONModel):
    setting: str = Field(description="the setting name the rule should apply ti")
    feature_values: Dict[str, str] = Field(description="the exact-match conditions of the rule")
    value: Any = Field(description="the value of the setting in contexts that match the rule")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="additional metadata of the rule")


class AddRuleOutput(ORJSONModel):
    rule_id: int


@router.post('', response_model=AddRuleOutput, status_code=status.HTTP_201_CREATED)
async def add_rule(input: AddRuleInput, app: HeksherApp = application):
    """
    add a rule, and get its ID
    """
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
    setting_names: List[str] = Field(description="a list of setting names to return the rules for")
    context_features_options: Dict[str, List[str]] = Field(
        description="a mapping of context features and possible values. Any rule with an exact-match condition not in"
                    " this mapping will not be returned"
    )
    cache_time: Optional[datetime] = Field(None, description="if provided, any settings that have not been changed"
                                                             " since this time will be ignored")
    include_metadata: bool = Field(False, description="whether to load and include the metadata of each rule in"
                                                      " the results")


class Rule(ORJSONModel):
    setting: str = Field(description="the setting the rule applies to")
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    context_features: List[Tuple[str, str]] = Field(description="a list of exact-match conditions for the rule")


class RuleWithMetadata(Rule):
    metadata: Dict[str, Any] = Field(description="the metadata of the rule, if requested")


class QueryRulesOutput(ORJSONModel):
    rules: List[Rule] = Field(description="the rules that matched the query")
    included_settings: List[str] = Field(description="the settings that were not filtered out of the query")


class QueryRulesOutputWithMetadata(ORJSONModel):
    rules: List[RuleWithMetadata] = Field(description="the rules that matched the query")
    included_settings: List[str] = Field(description="the settings that were not filtered out of the query")


@router.get('/query', response_model=Union[QueryRulesOutputWithMetadata, QueryRulesOutput])
async def query_rules(input: QueryRulesInput, app: HeksherApp = application):
    """
    query settings for rules for a specific set of potential contexts
    """
    not_context_features = await app.db_logic.get_not_context_features(input.context_features_options)
    if not_context_features:
        return PlainTextResponse(f'the following are not valid context features: {not_context_features}',
                                 status_code=status.HTTP_404_NOT_FOUND)

    not_settings = await app.db_logic.get_not_settings(input.setting_names)
    if not_settings:
        return PlainTextResponse(f'the following are not setting names: {not_settings}',
                                 status_code=status.HTTP_404_NOT_FOUND)

    query_result = await app.db_logic.query_rules(input.setting_names, input.context_features_options,
                                                  input.cache_time, input.include_metadata)
    rules = query_result.rules
    settings = query_result.applicable_settings

    if input.include_metadata:
        return QueryRulesOutputWithMetadata(
            included_settings=settings,
            rules=[
                RuleWithMetadata(setting=rule.setting, value=rule.value, context_features=rule.feature_values,
                                 metadata=rule.metadata)
                for rule in rules
            ])
    else:
        return QueryRulesOutput(
            included_settings=settings,
            rules=[
                Rule(setting=rule.setting, value=rule.value, context_features=rule.feature_values)
                for rule in rules
            ])


class GetRuleOutput(ORJSONModel):
    setting: str = Field(description="the setting the rule applies to")
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    feature_values: List[Tuple[str, str]] = Field(description="a list of exact-match conditions for the rule")
    metadata: Dict[str, Any] = Field(description="the metadata of the rule")


@router.get('/{rule_id}', response_model=GetRuleOutput)
async def get_rule(rule_id: int, app: HeksherApp = application):
    rule_spec = await app.db_logic.get_rule(rule_id)

    if not rule_spec:
        return PlainTextResponse('rule with id not found', status_code=status.HTTP_404_NOT_FOUND)

    return GetRuleOutput(setting=rule_spec.setting, value=rule_spec.value,
                         feature_values=rule_spec.feature_values, metadata=rule_spec.metadata)


v1_router.include_router(router)
