from asyncio import gather
from datetime import datetime
from typing import Optional, Any, Mapping, Collection, List

import orjson
from sqlalchemy import select, join

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import settings, configurable, context_features
from heksher.setting import Setting
from heksher.setting_types import setting_type


class SettingMixin(DBLogicBase):
    async def get_not_settings(self, names: List[str]) -> Collection[str]:
        names = ', '.join(f"('{n}')" for n in names)

        query = f"""
        SELECT n
        FROM (VALUES {names}) AS NAMES (n)
        WHERE NOT EXISTS (
          SELECT *
          FROM settings
          where settings.name = n
        )
        """

        results = await self.db.fetch_all(query)
        return [row['n'] for row in results]

    async def get_setting(self, name: str) -> Optional[Setting]:
        data_row, configurable_rows = await gather(
            self.db.fetch_one(
                select([settings.c.type, settings.c.default_value, settings.c.last_touch_time,
                        settings.c.metadata]).where(settings.c.name == name),

            ),
            self.db.fetch_all(
                select([configurable.c.context_feature])
                    .select_from(join(configurable, context_features,
                                      configurable.c.context_feature == context_features.c.name))
                    .where(configurable.c.setting == name)
                    .order_by(context_features.c.index)
            )
        )
        if data_row is None:
            return None

        configurable_ = [row['context_feature'] for row in configurable_rows]
        type_ = setting_type(data_row['type'])
        metadata_ = orjson.loads(data_row['metadata'])
        default_value_ = orjson.loads(data_row['default_value'])
        return Setting(
            name,
            type_,
            default_value_,
            data_row['last_touch_time'],
            configurable_,
            metadata_
        )

    async def insert_setting(self, setting: Setting):
        async with self.db.transaction():
            await self.db.execute(
                settings.insert().values(
                    name=setting.name,
                    type=str(setting.type),
                    default_value=str(orjson.dumps(setting.default_value), 'utf-8'),
                    last_touch_time=setting.last_touch_time,
                    metadata=str(orjson.dumps(setting.metadata), 'utf-8')
                )
            )
            await self.db.execute_many(
                configurable.insert(),
                [{'setting': setting.name, 'context_feature': cf} for cf in setting.configurable_features]
            )

    async def update_setting(self, name: str, changed: Mapping[str, Any], new_contexts):
        async with self.db.transaction():
            if changed:
                await self.db.execute(
                    settings.update().where(settings.c.name == name).values(**changed)
                )
            if new_contexts:
                await self.db.execute_many(
                    configurable.insert(),
                    [{'setting': name, 'context_feature': cf} for cf in new_contexts]
                )

    async def touch_setting(self, name: str, timestamp: Optional[datetime] = None):
        timestamp = timestamp or datetime.now()
        await self.db.execute(
            settings.update().where(settings.c.name == name).values(last_touch_time=timestamp)
        )

    async def delete_setting(self, name: str) -> bool:
        async with self.db.transaction():
            return (await self.db.fetch_val("""
            WITH n AS (DELETE FROM settings WHERE name = :name RETURNING *)
            SELECT COUNT(*) FROM n;
            """, {'name': name})) == 1

    async def get_settings(self) -> List[str]:
        records = await self.db.fetch_all(select([settings.c.name]))
        return [row['name'] for row in records]
