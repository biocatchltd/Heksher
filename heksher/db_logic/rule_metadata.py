from typing import Any, Dict

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import rule_metadata


class RuleMetadataMixin(DBLogicBase):
    async def update_rule_metadata(self, rule_id: int, metadata: Dict[str, Any]):
        """
        Update the metadata of the given rule. Similar to the dict.update() method, meaning that for existing keys,
        the value will be updated, and new keys will be added as well.
        Args:
            rule_id: the id of the rule to update it's metadata.
            metadata: the metadata to update.
        """
        async with self.db_engine.begin() as conn:
            stmt = insert(rule_metadata).values(
                [{'rule': rule_id, 'key': k, 'value': v} for (k, v) in metadata.items()]
            )
            await conn.execute(stmt.on_conflict_do_update(index_elements=[rule_metadata.c.rule, rule_metadata.c.key],
                                                          set_={"value": stmt.excluded.value}))

    async def replace_rule_metadata(self, rule_id: int, new_metadata: Dict[str, Any]):
        """
        Replace the metadata of the given rule with new metadata.
        Args:
             rule_id: the id of  the rule to change its metadata.
             new_metadata: the new metadata for the rule.
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(rule_metadata.delete()
                               .where(rule_metadata.c.rule == rule_id)
                               )
            await conn.execute(
                rule_metadata.insert().values(
                    [{'rule': rule_id, 'key': k, 'value': v} for (k, v) in new_metadata.items()]
                )
            )

    async def update_rule_metadata_key(self, rule_id: int, key: str, new_value: Any):
        """
        Updates a specific key of the rule's metadata.
        Args:
            rule_id: the id of the rule to change its metadata.
            key: the key to update.
            new_value: the value to update for the given key.
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(insert(rule_metadata)
                               .values([{'rule': rule_id, 'key': key, 'value': new_value}])
                               .on_conflict_do_update(index_elements=[rule_metadata.c.rule,
                                                                      rule_metadata.c.key],
                                                      set_={"value": new_value}))

    async def delete_rule_metadata(self, rule_id: int):
        """
        Remove a rule's metadata from the DB
        Args:
            rule_id: the id of the rule to remove its metadata
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(rule_metadata.delete().where(rule_metadata.c.rule == rule_id))

    async def delete_rule_metadata_key(self, rule_id: int, key: str):
        """
        Remove a specific key from the rule's metadata
        Args:
            rule_id: the name of the rule
            key: the name of the key to be deleted from the rule metadata
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(rule_metadata.delete()
                               .where(and_(rule_metadata.c.rule == rule_id,
                                           rule_metadata.c.key == key)))
