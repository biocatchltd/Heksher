import re
from logging import getLogger
from typing import Any, Dict, List, Optional, Tuple, Union

from fastapi import Query
from pydantic import Field
from starlette import status
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from heksher.api.v1.util import ORJSONModel, PydanticResponse, application, handle_etag, router as v1_router
from heksher.api.v1.validation import MetadataKey
from heksher.app import HeksherApp
from heksher.db_logic.context_feature import db_get_not_found_context_features
from heksher.db_logic.rule import db_query_rules
from heksher.db_logic.setting import db_get_canonical_names, db_get_settings

logger = getLogger(__name__)


# https://github.com/tiangolo/fastapi/issues/2724
class QueryRulesOutput_Rule(ORJSONModel):
    value: Any = Field(description="the value of the setting in contexts where the rule matches")
    context_features: List[Tuple[str, str]] = Field(
        description="a list of exact-match conditions for the rule, in hierarchical order"
    )
    rule_id: int = Field(description="unique identifier of the rule.")


class QueryRulesOutput_Setting(ORJSONModel):
    default_value: Any = Field(description="the default value of the setting")
    rules: List[QueryRulesOutput_Rule] = Field(description="a list of rules for the setting")


class QueryRulesOutput(ORJSONModel):
    settings: Dict[str, QueryRulesOutput_Setting] = Field(description="query results for each setting")


class QueryRulesOutputWithMetadata_Rule(QueryRulesOutput_Rule):
    metadata: Dict[MetadataKey, Any] = Field(description="the metadata of the rule, if requested")


class QueryRulesOutputWithMetadata_Setting(ORJSONModel):
    default_value: Any = Field(description="the default value of the setting")
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


@v1_router.get('/query', response_model=Union[QueryRulesOutputWithMetadata, QueryRulesOutput])  # type: ignore
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
    async with app.engine.connect() as conn:
        if raw_settings is None:
            all_settings = await db_get_settings(conn, include_configurable_features=False,
                                                 include_aliases=False,
                                                 include_metadata=False)
            settings = list(all_settings.keys())
            defaults = {k: v.default_value for (k, v) in all_settings.items()}
        elif not raw_settings:
            settings = []
            defaults = {}
        else:
            names = raw_settings.split(',')
            aliases = await db_get_canonical_names(conn, names)
            not_settings = [k for k, v in aliases.items() if not v]
            if not_settings:
                return PlainTextResponse(f'the following are not setting names: {not_settings}',
                                         status_code=status.HTTP_404_NOT_FOUND)
            settings = list(aliases.values())
            settings_data = await db_get_settings(conn, include_configurable_features=False,
                                                  include_aliases=False,
                                                  include_metadata=False, setting_names=settings)
            defaults = {k: v.default_value for (k, v) in settings_data.items()}

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

            not_context_features = await db_get_not_found_context_features(conn, context_features_options)
            if not_context_features:
                logger.info("unknown context features included in query",
                            extra={'unknown_context_features': list(not_context_features)})
                for cf in not_context_features:
                    del context_features_options[cf]
        results = await db_query_rules(conn, settings, context_features_options, include_metadata)
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
                    ], default_value=defaults[setting]) for setting, rules in results.items()
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
                    ], default_value=defaults[setting]) for setting, rules in results.items()
            })
    response = PydanticResponse(ret)
    handle_etag(response, request)
    return response
