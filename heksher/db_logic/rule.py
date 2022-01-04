from __future__ import annotations

from itertools import groupby
from operator import itemgetter
from typing import Any, Dict, List, Mapping, NamedTuple, Optional, Sequence, Tuple

import orjson
from sqlalchemy import and_, func, join, not_, select, tuple_
from sqlalchemy.ext.asyncio import AsyncConnection

from heksher.db_logic.metadata import conditions, context_features, rule_metadata, rules


class RuleSpec(NamedTuple):
    """
    A single rule that results from a rule query or lookup
    """
    setting: str
    value: Any
    feature_values: Sequence[Tuple[str, str]]
    metadata: Optional[Dict[str, Any]]


class InnerRuleSpec(NamedTuple):
    value: Any
    feature_values: Sequence[Tuple[str, str]]
    metadata: Optional[Dict[str, Any]]
    rule_id: int


class BareRuleSpec(NamedTuple):
    rule_id: int
    value: Any


async def db_get_rule(conn: AsyncConnection, id_: int, include_metadata: bool) -> Optional[RuleSpec]:
    basic_results = (await conn.execute(
        select([rules.c.setting, rules.c.value]).where(rules.c.id == id_).limit(1)
    )).mappings().first()
    if not basic_results:
        # rule does not exist
        return None
    feature_values = (await conn.execute(
        select([conditions.c.context_feature, conditions.c.feature_value])
        .select_from(join(conditions, context_features,
                          conditions.c.context_feature == context_features.c.name))
        .where(conditions.c.rule == id_)
        .order_by(context_features.c.index)
    )).mappings().all()
    if include_metadata:
        metadata_ = dict((await conn.execute(
            select([rule_metadata.c.key, rule_metadata.c.value])
            .where(rule_metadata.c.rule == id_)
        )).all())
    else:
        metadata_ = None

    value_ = orjson.loads(basic_results['value'])
    return RuleSpec(
        basic_results['setting'],
        value_,
        [(f['context_feature'], f['feature_value']) for f in feature_values],
        metadata_
    )


async def db_get_rules_feature_values(conn: AsyncConnection, ids: List[int]) -> Mapping[int, Sequence[Tuple[str, str]]]:
    feature_values = (await conn.execute(
        select([conditions.c.rule, conditions.c.context_feature, conditions.c.feature_value])
        .select_from(join(conditions, context_features,
                          conditions.c.context_feature == context_features.c.name))
        .where(conditions.c.rule.in_(ids))
        .order_by(context_features.c.index))).all()

    ret: Dict[int, List[Tuple[str, str]]] = {k: [] for k in ids}
    for rule_id, feature, value in feature_values:
        ret[rule_id].append((feature, value))
    return ret


async def db_get_rule_id(conn: AsyncConnection, setting: str, match_conditions: Dict[str, str]) -> Optional[int]:
    condition_count = len(match_conditions)
    condition_tuples = list(match_conditions.items())

    setting_rules = rules.select().where(rules.c.setting == setting).subquery()

    stmt = select(setting_rules.c.id.distinct()) \
        .where(
        # to make sure there is an exact-match to the given conditions,
        # check the amount of conditions for the rule alongside testing there are no other conditions not
        # specified by user
        and_(
            select(func.count()).select_from(conditions)
            .where(conditions.c.rule == setting_rules.c.id).scalar_subquery()
            == condition_count,  # amount of conditions
            not_(conditions.select()
                 .where(  # for better performance (speed wise), do the negative check
                and_(conditions.c.rule == setting_rules.c.id,
                     tuple_(conditions.c.context_feature, conditions.c.feature_value)
                     .not_in(condition_tuples)))
                 .exists())
        )
    )
    resp = await conn.execute(stmt)
    return resp.scalar_one_or_none()


async def db_delete_rule(conn: AsyncConnection, rule_id: int):
    """
    Delete a rule from the DB
    Args:
        rule_id: the id of the rule to delete
    """
    await conn.execute(rules.delete().where(rules.c.id == rule_id))


async def db_add_rule(conn: AsyncConnection, setting: str, value: Any, metadata: Dict[str, Any],
                      match_conditions: Dict[str, str]) -> int:
    """
    Add a rule to the DB

    Returns:
        The id of the newly-created rule

    Notes:
        The caller must ensure that the rule does not exist prior
    """
    value_ = str(orjson.dumps(value), 'utf-8')
    rule_id = (await conn.execute(
        rules.insert()
        .values(setting=setting, value=value_)
        .returning(rules.c.id)
    )).scalar_one()
    await conn.execute(
        conditions.insert().values(
            [{'rule': rule_id, 'context_feature': k, 'feature_value': v}
             for (k, v) in match_conditions.items()])
    )
    if metadata:
        await conn.execute(
            rule_metadata.insert().values(
                [{'rule': rule_id, 'key': k, 'value': v} for (k, v) in metadata.items()]
            )
        )
    return rule_id


async def db_patch_rule(conn: AsyncConnection, rule_id: int, value: Any) -> None:
    encoded_value = str(orjson.dumps(value), 'utf-8')
    await conn.execute(rules.update().where(rules.c.id == rule_id).values(value=encoded_value))


async def db_query_rules(conn: AsyncConnection, setting_names: List[str],
                         feature_value_options: Optional[Dict[str, Optional[List[str]]]],
                         include_metadata: bool) -> Dict[str, List[InnerRuleSpec]]:
    """
    Search the rules of multiple settings

    Args:
        conn: the DB connection
        setting_names: The names of the settings to query.
        feature_value_options: The options for each context feature. Rules that cannot match with these options are
         discounted. If None, all rules are counted
        include_metadata: Whether to retrieve and include the metadata of each rule in the result.

    Returns:
        A mapping of non-filtered settings to rules

    """
    applicable_rules: Dict[int, Tuple[Tuple[str, str], ...]] = {}
    conditions_ = conditions.alias()

    if not setting_names:
        # shortcut in case no settings are selected
        return {}
    else:
        # inv_match is a mixin condition, if an exact-match condition returns True for it, the rule associated with
        # it will not be returned
        if feature_value_options is None:
            # match all
            inv_match = False
        elif not feature_value_options:
            # match none
            inv_match = True
        else:
            exact_tuple_conditions = []
            only_cf_conditions = []
            for k, v in feature_value_options.items():
                if v is None:
                    only_cf_conditions.append(k)
                else:
                    for cf_value in v:
                        exact_tuple_conditions.append((k, cf_value))
            tuple_conditions = tuple_(conditions_.c.context_feature, conditions_.c.feature_value).not_in(
                exact_tuple_conditions)
            cf_conditions = conditions_.c.context_feature.not_in(only_cf_conditions)
            if exact_tuple_conditions and only_cf_conditions:
                inv_match = and_(tuple_conditions, cf_conditions)
            else:
                inv_match = tuple_conditions if exact_tuple_conditions else cf_conditions

        clauses = [
            not_(conditions_.select()
                 .where(
                and_(
                    conditions.c.rule == conditions_.c.rule, inv_match
                ))
                 .exists()),
            rules.c.setting.in_(setting_names)
        ]

        query = (select()
                 .add_columns(rules.c.id, conditions.c.context_feature, conditions.c.feature_value)
                 .select_from(rules.outerjoin(conditions, rules.c.id == conditions.c.rule))
                 .outerjoin(context_features, context_features.c.name == conditions.c.context_feature)
                 .where(*clauses)
                 .order_by(rules.c.id, context_features.c.index))

        conditions_results = (await conn.execute(query)).mappings().all()
        # group all the conditions by rules
        for rule_id, rows in groupby(conditions_results, key=itemgetter('id')):
            rule_conditions = tuple((row['context_feature'], row['feature_value']) for row in rows)
            if rule_conditions == ((None, None),):
                # this will occur if a rule has no exact-match conditions (i.e. it is a wildcard on all features)
                # though we don't support users entering rules without conditions, we nevertheless prepare against
                # them existing in the DB
                rule_conditions = ()
            applicable_rules[rule_id] = rule_conditions

        # finally, get all the actual data for each rule
        rule_query = (
            select([rules.c.id, rules.c.setting, rules.c.value])
            .where(rules.c.id.in_(applicable_rules))
            .order_by(rules.c.setting, rules.c.id)
        )
        rule_results = (await conn.execute(rule_query)).mappings().all()

        if include_metadata:
            metadata_results = (await conn.execute(
                select([rule_metadata.c.rule, rule_metadata.c.key, rule_metadata.c.value])
                .where(rule_metadata.c.rule.in_(applicable_rules))
                .order_by(rule_metadata.c.rule)
            )).all()
            metadata = {
                rule_id: {k: v for (_, k, v) in rows}
                for (rule_id, rows) in groupby(metadata_results, key=itemgetter(0))
            }
        else:
            metadata = None

    ret: Dict[str, List[InnerRuleSpec]] = {setting: [] for setting in setting_names}
    for setting, rows in groupby(rule_results, key=itemgetter('setting')):
        rule_list = [
            InnerRuleSpec(
                orjson.loads(row['value']),
                applicable_rules[row['id']],
                metadata.get(row['id'], {}) if metadata is not None else None,
                row['id']
            )
            for row in rows
        ]
        ret[setting] = rule_list
    return ret


async def db_get_rules_for_setting(conn: AsyncConnection, setting_name: str) -> Sequence[BareRuleSpec]:
    result = (await conn.execute(select([rules.c.id, rules.c.value]).where(rules.c.setting == setting_name))).all()
    return [BareRuleSpec(id_, orjson.loads(v)) for id_, v in result]


async def db_get_actual_configurable_features(conn: AsyncConnection, setting_name: str) -> Dict[str, List[int]]:
    """
    Get all the rules that are configured for each context feature for a setting
    """
    results = (await conn.execute(
        select([conditions.c.context_feature, rules.c.id])
        .select_from(rules.join(conditions, rules.c.id == conditions.c.rule))
        .where(rules.c.setting == setting_name)
        .order_by(conditions.c.context_feature)
    )).all()

    return {context_feature: [rule_id for (_, rule_id) in rows]
            for (context_feature, rows) in groupby(results, key=itemgetter(0))}
