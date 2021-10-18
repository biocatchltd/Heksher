from datetime import datetime
from logging import getLogger
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

from fastapi import APIRouter, Response
from pydantic import Field, validator
from starlette import status
from starlette.responses import PlainTextResponse

from heksher.api.v1.rules_metadata import router as metadata_router
from heksher.api.v1.util import ORJSONModel, application, router as v1_router
from heksher.api.v1.validation import ContextFeatureName, ContextFeatureValue, MetadataKey, SettingName
from heksher.app import HeksherApp
from heksher.setting import Setting

router = APIRouter(prefix='/rules')
logger = getLogger(__name__)


@router.delete('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def delete_rule(rule_id: int, app: HeksherApp = application):
    """
    Remove a rule.
    """
    rule_spec = await app.db_logic.get_rule(rule_id, include_metadata=False)

    if not rule_spec:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    await app.db_logic.delete_rule(rule_id)
    await app.db_logic.touch_setting(rule_spec.setting)


class SearchRuleInput(ORJSONModel):
    setting: SettingName = Field(description="the setting name the rule belongs to")
    feature_values: Dict[ContextFeatureName, ContextFeatureValue] = \
        Field(description="the exact-match conditions of the rule")

    @validator('feature_values')
    @classmethod
    def feature_values_not_empty(cls, v):
        if not v:
            raise ValueError('feature_values must not be empty')
        return v


class SearchRuleOutput(ORJSONModel):
    rule_id: int


@router.post('/search', response_model=SearchRuleOutput)
async def search_rule(input: SearchRuleInput, app: HeksherApp = application):
    """
    Get the ID of a rule with specific conditions.
    """
    rule_id = await app.db_logic.get_rule_id(input.setting, input.feature_values)
    if not rule_id:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    return SearchRuleOutput(rule_id=rule_id)


class AddRuleInput(ORJSONModel):
    setting: SettingName = Field(description="the setting name the rule should apply to")
    feature_values: Dict[ContextFeatureName, ContextFeatureValue] = \
        Field(description="the exact-match conditions of the rule")
    value: Any = Field(description="the value of the setting in contexts that match the rule")
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
    setting: Optional[Setting] = await app.db_logic.get_setting(input.setting, include_metadata=False)
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


class PatchRuleInput(ORJSONModel):
    value: Any = Field(description="the value of the setting in contexts that match the rule")


@router.patch('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def patch_rule(rule_id: int, input: PatchRuleInput, app: HeksherApp = application):
    """
    Modify existing rule's value
    """
    rule = await app.db_logic.get_rule(rule_id, include_metadata=False)
    if not rule:
        return PlainTextResponse(status_code=status.HTTP_404_NOT_FOUND)

    setting = await app.db_logic.get_setting(rule.setting, include_metadata=False)
    assert setting

    if not setting.type.validate(input.value):
        return PlainTextResponse(f'rule value is incompatible with setting type {setting.type}',
                                 status_code=status.HTTP_400_BAD_REQUEST)

    await app.db_logic.patch_rule(rule_id, input.value)
    await app.db_logic.touch_setting(setting.name)


class QueryRulesInput(ORJSONModel):
    setting_names: List[SettingName] = Field(description="a list of setting names to return the rules for")
    context_features_options: Union[
        Dict[ContextFeatureName, Union[
            List[ContextFeatureValue], Literal['*']
        ]],
        Literal['*']
    ] = Field(
        description="a mapping of context features and possible values. Any rule with an exact-match condition not in"
                    " this mapping will not be returned. Optionally can be set to '*' to return all rules, or set an"
                    " individual context feature to '*' to not disqualify rules with conditions on that context"
                    " feature."
    )
    cache_time: Optional[datetime] = Field(None, description="if provided, any settings that have not been changed"
                                                             " since this time will be ignored")
    include_metadata: bool = Field(False, description="whether to load and include the metadata of each rule in"
                                                      " the results")

    @validator('context_features_options')
    @classmethod
    def wildcard(cls, v):
        if v == '*':
            return None
        for k in v.keys():
            if v[k] == '*':
                v[k] = None
            elif not v[k]:
                raise ValueError('cannot accept an empty option')
        return v

    @validator('cache_time')
    @classmethod
    def no_tz(cls, v: Optional[datetime]):
        if v and v.tzinfo:
            raise ValueError('cannot accept datetime with timezone')
        return v

    @validator('cache_time')
    @classmethod
    def no_future(cls, v: Optional[datetime]):
        now = datetime.utcnow()
        if now < v:
            raise ValueError('got cache time in the future')
        return v

    @property
    def valid_context_features_options(cls) -> Optional[Dict[str, Optional[List[str]]]]:
        return cls.context_features_options  # type: ignore


# https://github.com/tiangolo/fastapi/issues/2724
class QueryRulesOutput_Rule(ORJSONModel):
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    context_features: List[Tuple[str, str]] = Field(
        description="a list of exact-match conditions for the rule, in hierarchical order"
    )
    rule_id: int = Field(description="unique identifier of the rule.")


class QueryRulesOutput(ORJSONModel):
    rules: Dict[str, List[QueryRulesOutput_Rule]] = Field(description="a list of rules for each setting that was not"
                                                                      " filtered out")


class QueryRulesOutputWithMetadata_Rule(QueryRulesOutput_Rule):
    metadata: Dict[MetadataKey, Any] = Field(description="the metadata of the rule, if requested")


class QueryRulesOutputWithMetadata(ORJSONModel):
    rules: Dict[str, List[QueryRulesOutputWithMetadata_Rule]] = Field(
        description="a list of rules for each setting that was not filtered out"
    )


@router.post('/query', response_model=Union[QueryRulesOutputWithMetadata, QueryRulesOutput])  # type: ignore
async def query_rules(input: QueryRulesInput, app: HeksherApp = application):
    """
    Query settings for rules for a specific set of potential contexts.
    """
    if input.context_features_options is not None:
        not_context_features = await app.db_logic.get_not_found_context_features(input.context_features_options)
        if not_context_features:
            return PlainTextResponse(f'the following are not valid context features: {not_context_features}',
                                     status_code=status.HTTP_404_NOT_FOUND)

    if input.setting_names:
        not_settings = await app.db_logic.get_not_found_setting_names(input.setting_names)
        if not_settings:
            return PlainTextResponse(f'the following are not setting names: {not_settings}',
                                     status_code=status.HTTP_404_NOT_FOUND)

        query_result = await app.db_logic.query_rules(input.setting_names, input.valid_context_features_options,
                                                      input.cache_time, input.include_metadata)
    else:
        query_result = {}

    if input.include_metadata:
        return QueryRulesOutputWithMetadata(
            rules={
                setting: [
                    QueryRulesOutputWithMetadata_Rule(
                        value=rule.value, context_features=rule.feature_values, metadata=rule.metadata,
                        rule_id=rule.rule_id
                    )
                    for rule in rules
                ] for setting, rules in query_result.items()
            })
    else:
        return QueryRulesOutput(
            rules={
                setting: [
                    QueryRulesOutput_Rule(value=rule.value, context_features=rule.feature_values, rule_id=rule.rule_id)
                    for rule in rules
                ] for setting, rules in query_result.items()
            })


class GetRuleOutput(ORJSONModel):
    setting: str = Field(description="the setting the rule applies to")
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    feature_values: List[Tuple[str, str]] = Field(description="a list of exact-match conditions for the rule")
    metadata: Dict[MetadataKey, Any] = Field(description="the metadata of the rule")


@router.get('/{rule_id}', response_model=GetRuleOutput)
async def get_rule(rule_id: int, app: HeksherApp = application):
    rule_spec = await app.db_logic.get_rule(rule_id, include_metadata=True)

    if not rule_spec:
        return Response(status_code=status.HTTP_404_NOT_FOUND)

    return GetRuleOutput(setting=rule_spec.setting, value=rule_spec.value,
                         feature_values=rule_spec.feature_values, metadata=rule_spec.metadata)


router.include_router(metadata_router)
v1_router.include_router(router)
