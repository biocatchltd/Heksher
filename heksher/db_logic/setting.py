from asyncio import gather
from datetime import datetime
from typing import Optional, Any, Mapping, Collection, List, Iterable

import orjson
from sqlalchemy import select, join

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import settings, configurable, context_features
from heksher.setting import Setting
from heksher.setting_types import setting_type


class SettingMixin(DBLogicBase):
    async def get_not_settings(self, names: Iterable[str]) -> Collection[str]:
        """
        Args:
            names: an iterable of potential setting names.

        Returns:
            A collection of names that have no settings with that name.

        """
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
        """
        Args:
            name: The name of a setting

        Returns:
            The setting object for the setting in the DB with the same name, or None if it does not exist

        """
        data_row, configurable_rows = await gather(
            self.db.fetch_one(
                select([settings.c.type, settings.c.default_value, settings.c.metadata]).where(settings.c.name == name)
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
            configurable_,
            metadata_
        )

    async def add_setting(self, setting: Setting):
        """
        Add a setting to the DB
        Args:
            setting: data of the new setting to add.
        """
        async with self.db.transaction():
            await self.db.execute(
                settings.insert().values(
                    name=setting.name,
                    type=str(setting.type),
                    default_value=str(orjson.dumps(setting.default_value), 'utf-8'),
                    last_touch_time=datetime.now(),
                    metadata=str(orjson.dumps(setting.metadata), 'utf-8')
                )
            )
            await self.db.execute_many(
                configurable.insert(),
                [{'setting': setting.name, 'context_feature': cf} for cf in setting.configurable_features]
            )

    async def update_setting(self, name: str, changed: Mapping[str, Any], new_contexts: Iterable[str]):
        """
        Edit an existing setting in the DB
        Args:
            name: The name of the setting to edit
            changed: The fields of the setting to change
            new_contexts: An iterable of new context names to assign to the setting as configurable
        """
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
        """
        Update a setting's last_touch_time
        Args:
            name: the name of the setting to update
            timestamp: the time to set the last_touch_time, defaults to datetime.now
        """
        timestamp = timestamp or datetime.now()
        await self.db.execute(
            settings.update().where(settings.c.name == name).values(last_touch_time=timestamp)
        )

    async def delete_setting(self, name: str) -> bool:
        """
        Remove a setting from the DB
        Args:
            name: the name of the setting to remove
        Returns:
            Whether a setting with the name was found
        """
        async with self.db.transaction():
            return (await self.db.fetch_val("""
            WITH n AS (DELETE FROM settings WHERE name = :name RETURNING *)
            SELECT COUNT(*) FROM n;
            """, {'name': name})) == 1

    async def get_settings(self) -> List[str]:
        """
        Returns:
            A list of all setting names in the DB
        """
        records = await self.db.fetch_all(select([settings.c.name]))
        return [row['name'] for row in records]
