from asyncio import gather
from typing import Optional, Dict, Any, Mapping

import orjson
from sqlalchemy import select

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import settings, configurable
from heksher.setting import Setting
from heksher.setting_types import setting_type


class SettingMixin(DBLogicBase):
    async def get_setting(self, name: str) -> Optional[Setting]:
        data_row, configurable_rows = await gather(
            self.db.fetch_one(
                select([settings.c.type, settings.c.default_value, settings.c.last_touch_time,
                        settings.c.metadata]).where(settings.c.name == name),

            ),
            self.db.fetch_all(
                select([configurable.c.context_feature]).where(configurable.c.setting == name)
            )
        )
        if data_row is None:
            return None

        configurable_ = frozenset(row['context_feature'] for row in configurable_rows)
        type_ = setting_type(data_row['type'])
        metadata_ = orjson.loads(data_row['metadata'])
        return Setting(
            name,
            type_,
            data_row['default_value'],
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
                configurable.insert().values(
                    setting=setting.name,
                    context_feature=':cf'
                ),
                [{'cf': cf} for cf in setting.configurable_features]
            )

    async def update_setting(self, name, changed: Mapping[str, Any]):
        await self.db.execute(
            settings.update().where(settings.c.name == name).values(changed)
        )
