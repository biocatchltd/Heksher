from __future__ import annotations

from asyncio.tasks import gather
from datetime import datetime
from itertools import groupby
from operator import itemgetter
from typing import Dict, Optional, Any, List, Tuple, NamedTuple, Sequence, Union

import orjson
from sqlalchemy import select, join

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import rules, conditions, settings, context_features


# This class should be used in the context of db logic api only
from heksher.db_logic.util import inline_sql


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
        # we query both the rule and its feature values at the same time. Meaning that if the rule does not exist,
        # we make 1 too many calls. However, we expect to make so few get_rule calls to non-existent rules that this
        # is negligible
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
        # we convert the conditions to a format that they can be queried with an "IN" condition
        # (no, parameterization doesn't work)
        condition_tuples = ','.join(
            f"({inline_sql(k)},{inline_sql(v)})" for (k, v) in match_conditions.items()
        )
        query_template = f'''
        SELECT DISTINCT id
        FROM (
          SELECT * from rules
          WHERE setting = :setting
        ) as rules
        WHERE (SELECT COUNT(*) FROM conditions WHERE rule = rules.id) = :condition_count
        AND NOT EXISTS (
          SELECT *
          from conditions
          WHERE rule = id AND (context_feature, feature_value) NOT IN ({condition_tuples})
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

    async def query_rules(self, setting_names: List[str],
                          feature_value_options: Optional[Dict[str, Optional[List[str]]]],
                          setting_touch_time_cutoff: Optional[datetime],
                          include_metadata: bool) -> Dict[str, List[InnerRuleSpec]]:
        """
        Search the rules of multiple settings

        Args:
            setting_names: The names of the settings to query.
            feature_value_options: The options for each context feature. Rules that cannot match with these options are
             discounted. If None, all rules are counted
            setting_touch_time_cutoff: If provided, will discount all rules pertaining to settings that have not been
             updated since  this time.
            include_metadata: Whether to retrieve and include the metadata of each rule in the result.

        Returns:
            A mapping of non-filtered settings to rules

        """
        if setting_touch_time_cutoff:
            settings_results = await self.db.fetch_all(
                select([settings.c.name])
                .where(
                    settings.c.name.in_(setting_names)
                    & (settings.c.last_touch_time >= setting_touch_time_cutoff)
                )
            )
            applicable_settings = [row['name'] for row in settings_results]
        else:
            applicable_settings = setting_names

        if not applicable_settings:
            # shortcut in case all settings are up-to-date
            applicable_rules = {}
            rule_results = []
        else:
            # inv_match is a mixin condition, if an exact-match condition returns True for it, the rule associated with
            # it will not be returned
            if feature_value_options is None:
                # match all
                inv_match = 'FALSE'
            elif not feature_value_options:
                # match none
                inv_match = 'TRUE'
            else:
                exact_tuple_conditions = []
                only_cf_conditions = []
                for k, v in feature_value_options.items():
                    # (no, parameterization doesn't work)
                    if v is None:
                        only_cf_conditions.append(inline_sql(k))
                    else:
                        for cf_value in v:
                            exact_tuple_conditions.append(f"({inline_sql(k)},{inline_sql(cf_value)})")
                inv_match_predicates = []
                if exact_tuple_conditions:
                    inv_match_predicates.append('(context_feature, feature_value) NOT IN (' + ','.join(exact_tuple_conditions)+')')
                if only_cf_conditions:
                    inv_match_predicates.append('context_feature NOT IN (' + ','.join(only_cf_conditions)+')')
                inv_match = ' AND '.join(inv_match_predicates)

            # (no, parameterization doesn't work)
            settings_container = ','.join(f"'{name}'" for name in applicable_settings)
            query = f"""
            SELECT rules.id, C.context_feature, C.feature_value -- get all the conditions for all the rules
            FROM
            (
                (SELECT * from rules where setting IN ({settings_container})) as rules
                LEFT JOIN
                conditions as C
                ON rules.id = C.rule
            )
            LEFT JOIN context_features ON context_features.name = C.context_feature
            WHERE NOT EXISTS (
              SELECT *
              from conditions
              WHERE rule = C.rule AND {inv_match}
            )
            ORDER BY rules.id, context_features.index;
            """
            conditions_results = await self.db.fetch_all(query)
            applicable_rules: Dict[int, Tuple[Tuple[str, str], ...]] = {}
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
                .order_by(rules.c.setting)
            )
            if include_metadata:
                rule_query.append_column(rules.c.metadata)
            rule_results = await self.db.fetch_all(rule_query)

        ret = {}
        missing_settings = set(applicable_settings)
        for setting, rows in groupby(rule_results, key=itemgetter('setting')):
            rule_list = [
                InnerRuleSpec(
                    orjson.loads(row['value']),
                    applicable_rules[row['id']],
                    orjson.loads(row['metadata']) if include_metadata else None,
                )
                for row in rows
            ]
            ret[setting] = rule_list
            missing_settings.remove(setting)
        for setting in missing_settings:
            ret[setting] = []
        return ret
