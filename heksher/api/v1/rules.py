import re
from logging import getLogger
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import APIRouter, Query, Response
from pydantic import Field, validator
from starlette import status
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from heksher.api.v1.rules_metadata import router as metadata_router
from heksher.api.v1.util import ORJSONModel, PydanticResponse, application, handle_etag, router as v1_router
from heksher.api.v1.validation import ContextFeatureName, ContextFeatureValue, MetadataKey, SettingName
from heksher.app import HeksherApp

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
    canon_setting = await app.db_logic.get_setting(setting, include_metadata=False, include_configurable_features=False,
                                                   include_aliases=False)  # for aliasing
    if not canon_setting:
        return Response(status_code=status.HTTP_404_NOT_FOUND)
    feature_values_dict: Dict[str, str] = dict(part.split(':') for part in feature_values.split(','))  # type: ignore
    rule_id = await app.db_logic.get_rule_id(canon_setting.name, feature_values_dict)
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
    setting = await app.db_logic.get_setting(input.setting, include_metadata=False, include_configurable_features=True,
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

    existing_rule = await app.db_logic.get_rule_id(setting.name, input.feature_values)
    if existing_rule:
        return PlainTextResponse('rule already exists', status_code=status.HTTP_409_CONFLICT)

    new_id = await app.db_logic.add_rule(setting.name, input.value, input.metadata, input.feature_values)

    return PydanticResponse(AddRuleOutput(rule_id=new_id),
                            headers={'Location': f'/{new_id}'}, status_code=status.HTTP_201_CREATED)


class PatchRuleInput(ORJSONModel):
    value: Any = Field(description="the value of the setting in contexts that match the rule")


@router.patch('/{rule_id}', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
@router.put('/{rule_id}/value', status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
async def patch_rule(rule_id: int, input: PatchRuleInput, app: HeksherApp = application):
    """
    Modify existing rule's value
    """
    rule = await app.db_logic.get_rule(rule_id, include_metadata=False)
    if not rule:
        return PlainTextResponse(status_code=status.HTTP_404_NOT_FOUND)

    setting = await app.db_logic.get_setting(rule.setting, include_metadata=False, include_aliases=False,
                                             include_configurable_features=False)
    assert setting

    if not setting.type.validate(input.value):
        return PlainTextResponse(f'rule value is incompatible with setting type {setting.type}',
                                 status_code=status.HTTP_400_BAD_REQUEST)

    await app.db_logic.patch_rule(rule_id, input.value)


# https://github.com/tiangolo/fastapi/issues/2724
class QueryRulesOutput_Rule(ORJSONModel):
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    context_features: List[Tuple[str, str]] = Field(
        description="a list of exact-match conditions for the rule, in hierarchical order"
    )
    rule_id: int = Field(description="unique identifier of the rule.")


class QueryRulesOutput_Setting(ORJSONModel):
    rules: List[QueryRulesOutput_Rule] = Field(description="a list of rules for the setting")


class QueryRulesOutput(ORJSONModel):
    settings: Dict[str, QueryRulesOutput_Setting] = Field(description="query results for each setting")


class QueryRulesOutputWithMetadata_Rule(QueryRulesOutput_Rule):
    metadata: Dict[MetadataKey, Any] = Field(description="the metadata of the rule, if requested")


class QueryRulesOutputWithMetadata_Setting(ORJSONModel):
    rules: List[QueryRulesOutputWithMetadata_Rule] = Field(description="a list of rules for the setting")


class QueryRulesOutputWithMetadata(ORJSONModel):
    settings: Dict[str, QueryRulesOutputWithMetadata_Setting] = Field(description="query results for each setting")


raw_context_feature_filters_pattern = r'''(?x)
(
    \*  # we allow an explicit global wildcard
    |
    [a-zA-Z_0-9]+:  # context feature name
    (
        \*  # accept any value
        |
        \(
            [a-zA-Z_0-9]+  # value
            (,[a-zA-Z_0-9]+)*  # additional values
        \)
    )
    (
    ,[a-zA-Z_0-9]+: (\* | \([a-zA-Z_0-9]+ (,[a-zA-Z_0-9]+)*\))  # additional filters
    )*
)?  # we also allow empty string to signify no rules could match
$
'''


@router.get('/query', response_model=Union[QueryRulesOutputWithMetadata, QueryRulesOutput])  # type: ignore
async def query_rules(request: Request, app: HeksherApp = application,
                      raw_settings: str = Query(None, alias='settings',
                                                description="a comma-separated list of setting names",
                                                regex='([a-zA-Z_0-9.]+(,[a-zA-Z_0-9.]+)*)?$'),
                      raw_context_filters: str = Query(
                          '*', alias='context_filters',
                          description="a comma-separated list of context feature filters",
                          regex=raw_context_feature_filters_pattern, example=["a:(X,Y),b:(Z),c:*", '*', 'a:*']),
                      include_metadata: bool = Query(False, description="whether to include rule metadata in the"
                                                                        " response"),
                      ):
    if raw_settings is None:
        settings = await app.db_logic.get_all_settings_names()
    elif not raw_settings:
        settings = []
    else:
        names = raw_settings.split(',')
        aliases = await app.db_logic.get_canonical_names(names)
        not_settings = [k for k, v in aliases.items() if not v]
        if not_settings:
            return PlainTextResponse(f'the following are not setting names: {not_settings}',
                                     status_code=status.HTTP_404_NOT_FOUND)
        settings = list(aliases.values())

    if raw_context_filters == '*':
        context_features_options: Optional[Dict[str, Optional[List[str]]]] = None
    else:
        context_filter_items = ((match['key'], (None if match['values'] is None else match['values'].split(',')))
                                for match in
                                re.finditer(r'(?P<key>[a-z]+):(\((?P<values>[^)]+)\)|\*)', raw_context_filters))
        context_features_options = {}
        for k, v in context_filter_items:
            if k in context_features_options:
                return PlainTextResponse(f'context name repeated in context filter: {k}',
                                         status_code=status.HTTP_400_BAD_REQUEST)
            context_features_options[k] = v

        not_context_features = await app.db_logic.get_not_found_context_features(context_features_options)
        if not_context_features:
            return PlainTextResponse(f'the following are not valid context features: {not_context_features}',
                                     status_code=status.HTTP_404_NOT_FOUND)
    results = await app.db_logic.query_rules(settings, context_features_options, include_metadata)
    if include_metadata:
        ret: Union[QueryRulesOutputWithMetadata, QueryRulesOutput] = QueryRulesOutputWithMetadata(
            settings={
                setting:
                    QueryRulesOutputWithMetadata_Setting(rules=[
                        QueryRulesOutputWithMetadata_Rule(
                            value=rule.value, context_features=rule.feature_values, metadata=rule.metadata,
                            rule_id=rule.rule_id
                        )
                        for rule in rules
                    ]) for setting, rules in results.items()
            })
    else:
        ret = QueryRulesOutput(
            settings={
                setting:
                    QueryRulesOutput_Setting(rules=[
                        QueryRulesOutput_Rule(
                            value=rule.value, context_features=rule.feature_values, metadata=rule.metadata,
                            rule_id=rule.rule_id
                        )
                        for rule in rules
                    ]) for setting, rules in results.items()
            })
    response = PydanticResponse(ret)
    handle_etag(response, request)
    return response


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
