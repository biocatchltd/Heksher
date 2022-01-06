from typing import Any, Dict

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from heksher.db_logic.metadata import rule_metadata


async def db_update_rule_metadata(conn: AsyncConnection, rule_id: int, metadata: Dict[str, Any]):
    """
    Update the metadata of the given rule. Similar to the dict.update() method, meaning that for existing keys,
    the value will be updated, and new keys will be added as well.
    """
    stmt = insert(rule_metadata).values(
        [{'rule': rule_id, 'key': k, 'value': v} for (k, v) in metadata.items()]
    )
    await conn.execute(stmt.on_conflict_do_update(index_elements=[rule_metadata.c.rule, rule_metadata.c.key],
                                                  set_={"value": stmt.excluded.value}))


async def db_replace_rule_metadata(conn: AsyncConnection, rule_id: int, new_metadata: Dict[str, Any]):
    """
    Replace the metadata of the given rule with new metadata..
    """
    await conn.execute(rule_metadata.delete()
                       .where(rule_metadata.c.rule == rule_id)
                       )
    await conn.execute(
        rule_metadata.insert().values(
            [{'rule': rule_id, 'key': k, 'value': v} for (k, v) in new_metadata.items()]
        )
    )


async def db_update_rule_metadata_key(conn: AsyncConnection, rule_id: int, key: str, new_value: Any):
    """
    Updates a specific key of the rule's metadata.
    """
    await conn.execute(insert(rule_metadata)
                       .values([{'rule': rule_id, 'key': key, 'value': new_value}])
                       .on_conflict_do_update(index_elements=[rule_metadata.c.rule,
                                                              rule_metadata.c.key],
                                              set_={"value": new_value}))


async def db_delete_rule_metadata(conn: AsyncConnection, rule_id: int):
    await conn.execute(rule_metadata.delete().where(rule_metadata.c.rule == rule_id))


async def db_delete_rule_metadata_key(conn: AsyncConnection, rule_id: int, key: str):
    await conn.execute(rule_metadata.delete()
                       .where(and_(rule_metadata.c.rule == rule_id,
                                   rule_metadata.c.key == key)))
