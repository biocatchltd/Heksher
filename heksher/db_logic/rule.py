from typing import Dict, NewType, Optional, Any

import orjson

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import rules, conditions

RuleId = NewType('RuleId', int)


class RuleMixin(DBLogicBase):
    async def get_rule_id(self, setting: str, match_conditions: Dict[str, str]) -> Optional[RuleId]:
        condition_count = len(match_conditions)
        condition_tuples = list(match_conditions.items())

        query_template = '''
        SELECT DISTINCT rules.id
        FROM conditions as C RIGHT JOIN (SELECT * from rules where setting = :setting) as rules
        ON rules.id = C.rule
        WHERE (SELECT COUNT(*) FROM conditions WHERE rule = C.rule) = :condition_count
        AND (
          SELECT COUNT(*)
          from conditions
          WHERE rule = C.rule AND (context_feature, feature_value) in :condition_tuples
        ) = :condition_count;
        '''

        return await self.db.fetch_val(
            query_template,
            {'setting': setting, 'condition_count': condition_count, 'condition_tuples': condition_tuples}
        )

    async def remove_rule(self, rule_id: RuleId):
        async with self.db.transaction():
            await self.db.execute(conditions.delete().where(conditions.c.rule == rule_id))
            await self.db.execute(rules.delete().where(rules.c.id == rule_id))

    async def add_rule(self, setting: str, value: Any, metadata: Dict[str, Any], match_conditions: Dict[str, str]):
        metadata_ = str(orjson.dumps(metadata), 'utf-8')
        value_ = str(orjson.dumps(value), 'utf-8')
        async with self.db.transaction():
            rule_id = await self.db.execute(
                rules.insert()
                    .values(setting=setting, value=value_, metadata=metadata_)
                    .returning(rules.c.id)
            )
            await self.db.execute_many(
                conditions.insert().values(
                    rule=rule_id,
                    context_feature=':cf',
                    feature_value=':fv',
                ),
                [{'cf': k, 'fv': v} for (k, v) in match_conditions.items()]
            )
