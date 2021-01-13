from __future__ import annotations

from asyncio.tasks import gather
from collections import defaultdict
from datetime import datetime
from typing import Dict, Optional, Any, List, DefaultDict, Tuple, NamedTuple

import orjson
from sqlalchemy import select, join

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import rules, conditions, settings, context_features


# These two classes should be used in the context of db logic api only

class QueryResult(NamedTuple):
    """
    The result of a rule query
    """
    applicable_settings: List[str]
    rules: List[RuleSpec]


class RuleSpec(NamedTuple):
    """
    A single rule that results from a rule query or lookup
    """
    setting: str
    value: Any
    feature_values: List[Tuple[str, str]]
    metadata: Optional[Dict[str, Any]]


class RuleMixin(DBLogicBase):
    async def get_rule(self, id_: int) -> Optional[RuleSpec]:
        """
        Args:
            id_: the id of a specific rule

        Returns:
            A RuleSpec describing the rule with the id, or None if no such rule exists.
        """
        basic_results, feature_values = await gather(
            self.db.fetch_one(
                select([rules.c.setting, rules.c.value, rules.c.metadata]).where(rules.c.id == id_)
            ),
            self.db.fetch_all(
                select([conditions.c.context_feature, conditions.c.feature_value])
                    .select_from(join(conditions, context_features,
                                      conditions.c.context_feature == context_features.c.name))
                    .where(conditions.c.rule == id_)
                    .order_by(context_features.c.index)
            )
        )
        if not basic_results:
            return None
        metadata_ = orjson.loads(basic_results['metadata'])
        value_ = orjson.loads(basic_results['value'])
        return RuleSpec(
            basic_results['setting'],
            value_,
            [(f['context_feature'], f['feature_value']) for f in feature_values],
            metadata_
        )

    async def get_rule_id(self, setting: str, match_conditions: Dict[str, str]) -> Optional[int]:
        """
        Lookup a rule by its settings and conditions, and retrieve its id

        Args:
            setting: The name of the setting the rule pertains to
            match_conditions: The exact-match conditions of the rule

        Returns:
            The id of the rule, or None if it does not exist

        """
        condition_count = len(match_conditions)
        condition_tuples = ','.join(f"('{k}','{v}')" for (k, v) in match_conditions.items())
        query_template = f'''
        SELECT DISTINCT rules.id
        FROM conditions as C
        RIGHT JOIN (
          SELECT * from rules
          WHERE setting = :setting
          AND (SELECT COUNT(*) FROM conditions WHERE rule = rules.id) = :condition_count
        ) as rules
        ON rules.id = C.rule
        WHERE NOT EXISTS (
          SELECT *
          from conditions
          WHERE rule = C.rule AND (context_feature, feature_value) NOT IN ({condition_tuples})
        );
        '''

        return await self.db.fetch_val(
            query_template,
            {'setting': setting, 'condition_count': condition_count}
        )

    async def delete_rule(self, rule_id: int):
        """
        Delete a rule from the DB
        Args:
            rule_id: the id of the rule to delete
        """
        await self.db.execute(rules.delete().where(rules.c.id == rule_id))

    async def add_rule(self, setting: str, value: Any, metadata: Dict[str, Any],
                       match_conditions: Dict[str, str]) -> int:
        """
        Add a rule to the DB
        Args:
            setting: The setting the rule pertains to
            value: The value of the setting where the rule matches
            match_conditions: The exact-match conditions of the rule
            metadata: additional metadata

        Returns:
            The id of the newly-created rule

        Notes:
            The caller must ensure that the rule does not exist prior
        """
        metadata_ = str(orjson.dumps(metadata), 'utf-8')
        value_ = str(orjson.dumps(value), 'utf-8')
        async with self.db.transaction():
            rule_id = await self.db.fetch_val(
                rules.insert()
                    .values(setting=setting, value=value_, metadata=metadata_)
                    .returning(rules.c.id)
            )
            await self.db.execute_many(
                conditions.insert(),
                [{'rule': rule_id, 'context_feature': k, 'feature_value': v} for (k, v) in match_conditions.items()]
            )
        return rule_id

    async def query_rules(self, setting_names: List[str], feature_value_options: Dict[str, List[str]],
                          cache_time: Optional[datetime], include_metadata: bool) -> QueryResult:
        """
        Search the rules of multiple settings

        Args:
            setting_names: The names of the settings to query.
            feature_value_options: The options for each context feature. Rules that cannot match with these options are
             discounted.
            cache_time: If provided, will discount all rules pertaining to settings that have not been updated since
             this time.
            include_metadata: Whether to retrieve and include the metadata of each rule in the result.

        Returns:
            A QueryResult

        """
        if cache_time:
            settings_results = await self.db.fetch_all(
                select([settings.c.name])
                    .where(
                    settings.c.name.in_(setting_names)
                    & (settings.c.last_touch_time >= cache_time)
                )
            )
            applicable_settings = [row['name'] for row in settings_results]
        else:
            applicable_settings = setting_names

        condition_tuples = ','.join(f"('{k}','{v}')" for (k, values) in feature_value_options.items() for v in values)
        settings_container = ','.join(f"'{name}'" for name in applicable_settings)

        query = f"""
        SELECT rules.id, C.context_feature, C.feature_value
        FROM (
        conditions as C RIGHT JOIN (SELECT * from rules where setting IN ({settings_container})) as rules
        ON rules.id = C.rule
        ) LEFT JOIN context_features ON context_features.name = C.context_feature
        WHERE NOT EXISTS (
          SELECT *
          from conditions
          WHERE rule = C.rule AND (context_feature, feature_value) NOT IN ({condition_tuples})
        )
        ORDER BY context_features.index;
        """
        conditions_results = await self.db.fetch_all(query)
        applicable_rules: DefaultDict[int, List[Tuple[str, str]]] = defaultdict(list)
        for row in conditions_results:
            if row['context_feature'] is None:
                # though we don't support users entering rules without conditions, we nevertheless prepare against it
                applicable_rules.setdefault(row['id'], [])
                continue
            applicable_rules[row['id']].append((row['context_feature'], row['feature_value']))

        rule_query = select([rules.c.id, rules.c.setting, rules.c.value]).where(rules.c.id.in_(applicable_rules))
        if include_metadata:
            rule_query.append_column(rules.c.metadata)
        rule_results = await self.db.fetch_all(rule_query)

        ret = []
        for row in rule_results:
            rule = RuleSpec(row['setting'],
                            orjson.loads(row['value']),
                            applicable_rules[row['id']],
                            orjson.loads(row['metadata']) if include_metadata else None)
            ret.append(rule)
        return QueryResult(applicable_settings, ret)
