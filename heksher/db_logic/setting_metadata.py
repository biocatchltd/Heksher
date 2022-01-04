from typing import Any, Dict

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from heksher.db_logic.metadata import setting_metadata
from heksher.db_logic.setting import db_bump_setting_version


async def db_update_setting_metadata(conn: AsyncConnection, name: str, metadata: Dict[str, Any], new_version: str):
    if metadata:
        stmt = insert(setting_metadata).values(
            [{'setting': name, 'key': k, 'value': v} for (k, v) in metadata.items()]
        )
        await conn.execute(stmt.on_conflict_do_update(index_elements=[setting_metadata.c.setting,
                                                                      setting_metadata.c.key],
                                                      set_={"value": stmt.excluded.value}))
    await db_bump_setting_version(conn, name, new_version)


async def db_replace_setting_metadata(conn: AsyncConnection, name: str, new_metadata: Dict[str, Any], new_version: str):
    await conn.execute(setting_metadata.delete()
                       .where(setting_metadata.c.setting == name)
                       )
    if new_metadata:
        await conn.execute(
            setting_metadata.insert().values(
                [{'setting': name, 'key': k, 'value': v} for (k, v) in new_metadata.items()]
            )
        )
    await db_bump_setting_version(conn, name, new_version)


async def db_update_setting_metadata_key(conn: AsyncConnection, name: str, key: str, new_value: Any, new_version: str):
    await conn.execute(insert(setting_metadata)
                       .values([{'setting': name, 'key': key, 'value': new_value}])
                       .on_conflict_do_update(index_elements=[setting_metadata.c.setting,
                                                              setting_metadata.c.key],
                                              set_={"value": new_value}))
    await db_bump_setting_version(conn, name, new_version)


async def db_delete_setting_metadata(conn: AsyncConnection, name: str, new_version: str):
    await conn.execute(setting_metadata.delete().where(setting_metadata.c.setting == name))
    await db_bump_setting_version(conn, name, new_version)


async def db_delete_setting_metadata_key(conn: AsyncConnection, name: str, key: str, new_version: str):
    await conn.execute(setting_metadata.delete()
                       .where(and_(setting_metadata.c.setting == name,
                                   setting_metadata.c.key == key)))
    await db_bump_setting_version(conn, name, new_version)
