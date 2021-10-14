from datetime import datetime
from itertools import groupby
from typing import Any, Collection, Dict, Iterable, List, Mapping, NamedTuple, Optional

import orjson
from _operator import itemgetter
from sqlalchemy import String, and_, column, join, not_, or_, select, values

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import configurable, context_features, setting_metadata, settings
from heksher.setting import Setting
from heksher.setting_types import setting_type


class SettingSpec(NamedTuple):
    name: str
    raw_type: Optional[str]
    default_value: Optional[Any]
    metadata: Optional[Dict[str, Any]]
    configurable_features: Optional[List[str]]


class SettingMixin(DBLogicBase):
    async def get_not_found_setting_names(self, names: Iterable[str]) -> Collection[str]:
        """
        Args:
            names: an iterable of potential setting names.

        Returns:
            A collection of names that have no settings with that name.

        """
        names_table = values(column('n', String), name='names').data(names)
        async with self.db_engine.connect() as conn:
            results = (await conn.execute(
                names_table.select()
                .where(not_(settings.select().where(settings.c.name == names_table.c.n).exists())))
                       ).scalars().all()

        return results

    async def get_setting(self, name: str, include_metadata: bool) -> Optional[Setting]:
        """
        Args:
            name: The name of a setting
            include_metadata: whether to include setting metadata
        Returns:
            The setting object for the setting in the DB with the same name, or None if it does not exist

        """
        async with self.db_engine.connect() as conn:
            data_row = (await conn.execute(
                select([settings.c.type, settings.c.default_value])
                .where(settings.c.name == name))
                        ).mappings().first()

            if data_row is None:
                return None

            configurable_rows = (await conn.execute(
                select([configurable.c.context_feature])
                .select_from(join(configurable, context_features,
                                  configurable.c.context_feature == context_features.c.name))
                .where(configurable.c.setting == name)
                .order_by(context_features.c.index))
                                 ).scalars().all()

            if include_metadata:
                metadata_ = dict((await conn.execute(
                    select([setting_metadata.c.key, setting_metadata.c.value])
                    .where(setting_metadata.c.setting == name)
                )).all())
            else:
                metadata_ = None

        type_ = setting_type(data_row['type'])
        default_value_ = orjson.loads(data_row['default_value'])
        return Setting(
            name,
            type_,
            default_value_,
            configurable_rows,
            metadata_
        )

    async def add_setting(self, setting: Setting):
        """
        Add a setting to the DB
        Args:
            setting: data of the new setting to add.
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(
                settings.insert().values(
                    name=setting.name,
                    type=str(setting.type),
                    default_value=str(orjson.dumps(setting.default_value), 'utf-8'),
                    last_touch_time=datetime.utcnow(),
                )
            )
            await conn.execute(
                configurable.insert().values(
                    [{'setting': setting.name, 'context_feature': cf} for cf in setting.configurable_features]
                )
            )
            if setting.metadata:
                await conn.execute(
                    setting_metadata.insert().values(
                        [{'setting': setting.name, 'key': k, 'value': v} for (k, v) in setting.metadata.items()]
                    )
                )

    async def update_setting(self, name: str, changed: Mapping[str, Any], new_contexts: Iterable[str],
                             new_metadata: Optional[Dict[str, Any]]):
        """
        Edit an existing setting in the DB
        Args:
            name: The name of the setting to edit
            changed: The fields of the setting to change
            new_contexts: An iterable of new context names to assign to the setting as configurable
            new_metadata: Optional, new metadata to assign to the setting
        """
        async with self.db_engine.begin() as conn:
            if changed:
                await conn.execute(
                    settings.update().where(settings.c.name == name).values(**changed)
                )
            if new_contexts:
                await conn.execute(
                    configurable.insert().values(
                        [{'setting': name, 'context_feature': cf} for cf in new_contexts]
                    )
                )
            if new_metadata is not None:
                await conn.execute(
                    setting_metadata.delete().where(setting_metadata.c.setting == name)
                )
                await conn.execute(
                    setting_metadata.insert().values(
                        [{'setting': name, 'key': k, 'value': v} for (k, v) in new_metadata.items()]
                    )
                )

    async def touch_setting(self, name: str, timestamp: Optional[datetime] = None):
        """
        Update a setting's last_touch_time
        Args:
            name: the name of the setting to update
            timestamp: the time to set the last_touch_time, defaults to datetime.now
        """
        timestamp = timestamp or datetime.utcnow()
        async with self.db_engine.begin() as conn:
            await conn.execute(
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
        async with self.db_engine.begin() as conn:
            resp = (await conn.execute(settings.delete().where(settings.c.name == name))).rowcount
        return resp == 1

    async def get_settings(self, full_data: bool) -> List[SettingSpec]:
        """
        Returns:
            A list of all setting names in the DB
        """
        select_query = select([settings.c.name]).order_by(settings.c.name)
        if full_data:
            select_query = select_query.add_columns(settings.c.type, settings.c.default_value)

        if full_data:
            async with self.db_engine.connect() as conn:
                records = (await conn.execute(select_query)).mappings().all()
                configurable_rows = (await conn.execute(
                    select([configurable.c.setting, configurable.c.context_feature])
                    .select_from(join(configurable, context_features,
                                      configurable.c.context_feature == context_features.c.name))
                    .order_by(configurable.c.setting, context_features.c.index)
                )).mappings().all()
                metadata_rows = await conn.execute(
                    select([setting_metadata.c.setting, setting_metadata.c.key, setting_metadata.c.value])
                    .order_by(setting_metadata.c.setting)
                )

            configurables = {
                setting: [row['context_feature'] for row in rows]
                for (setting, rows) in groupby(configurable_rows, key=itemgetter('setting'))
            }
            metadata = {
                setting: {k: v for (_, k, v) in rows} for (setting, rows) in groupby(metadata_rows, key=itemgetter(0))
            }
        else:
            async with self.db_engine.connect() as conn:
                records = (await conn.execute(select_query)).mappings().all()
            configurables = {}
            metadata = None

        return [
            SettingSpec(
                row['name'],
                row['type'] if full_data else None,
                orjson.loads(row['default_value']) if full_data else None,
                metadata.get(row['name'], {}) if full_data else None,
                configurables[row['name']] if full_data else None
            ) for row in records
        ]

    async def update_setting_metadata(self, name: str, metadata: Dict[str, Any]):
        """
        Update the metadata of the given setting. Similar to the dict.update() method, meaning that for existing keys,
        the value will be updated, and new keys will be added as well.
        Args:
            name: the name of the setting to update it's metadata.
            metadata: the metadata to update.
        """
        async with self.db_engine.begin() as conn:
            # first, delete the keys that already exists in the table
            await conn.execute(setting_metadata.delete()
                               .where(and_(setting_metadata.c.setting == name,
                                           or_(setting_metadata.c.key == key for key in metadata.keys())))
                               )
            # after this, we can insert the new metadata
            await conn.execute(
                setting_metadata.insert().values(
                    [{'setting': name, 'key': k, 'value': v} for (k, v) in metadata.items()]
                )
            )

    async def replace_setting_metadata(self, name: str, new_metadata: Dict[str, Any]):
        """
        Replace the metadata of the given setting with new metadata.
        Args:
             name: the name of the setting to change its metadata.
             new_metadata: the new metadata for the setting.
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(setting_metadata.delete()
                               .where(setting_metadata.c.setting == name)
                               )
            await conn.execute(
                setting_metadata.insert().values(
                    [{'setting': name, 'key': k, 'value': v} for (k, v) in new_metadata.items()]
                )
            )

    async def update_setting_metadata_key(self, name: str, key: str, new_value: Any):
        """
        Updates a specific key of the setting's metadata.
        Args:
            name: the name of the setting to change its metadata.
            key: the key to update.
            new_value: the value to update for the given key.
        """
        async with self.db_engine.begin() as conn:
            key_exists = (
                await conn.execute(select([setting_metadata.c.key])
                                   .where(and_(setting_metadata.c.setting == name,
                                               setting_metadata.c.key == key)))
            ).scalar_one_or_none()
            if key_exists:
                await conn.execute(setting_metadata.update()
                                   .where(and_(setting_metadata.c.setting == name,
                                               setting_metadata.c.key == key))
                                   .values(value=new_value))
            else:
                await conn.execute(setting_metadata.insert()
                                   .values([{'setting': name, 'key': key, 'value': new_value}]))

    async def delete_setting_metadata(self, name: str):
        """
        Remove a setting's metadata from the DB
        Args:
            name: the name of the setting to remove its metadata
        Returns:
            Whether a setting with the name was found
        """
        async with self.db_engine.begin() as conn:
            resp = (await conn.execute(setting_metadata.delete().where(setting_metadata.c.setting == name))).rowcount
        return resp >= 1

    async def get_setting_metadata(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Args:
            name: the setting to get its metadata.
        Returns:
            the metadata of the setting.
        """
        async with self.db_engine.connect() as conn:
            record = (
                await conn.execute(select([setting_metadata.c.key, setting_metadata.c.value])
                                   .where(setting_metadata.c.setting == name))
            ).mappings().all()
        if record:
            return {row["key"]: row["value"] for row in record}
        else:
            return {}
