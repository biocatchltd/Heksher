from datetime import datetime
from itertools import groupby
from typing import Any, Collection, Dict, Iterable, List, Mapping, NamedTuple, Optional

import orjson
from _operator import itemgetter
from sqlalchemy import String, column, join, not_, select, values

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import configurable, context_features, settings
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

    async def get_setting(self, name: str) -> Optional[Setting]:
        """
        Args:
            name: The name of a setting

        Returns:
            The setting object for the setting in the DB with the same name, or None if it does not exist

        """
        async with self.db_engine.connect() as conn:
            data_row = (await conn.execute(
                select([settings.c.type, settings.c.default_value, settings.c.metadata])
                .where(settings.c.name == name))
                        ).mappings().first()

            configurable_rows = (await conn.execute(
                select([configurable.c.context_feature])
                .select_from(join(configurable, context_features,
                                  configurable.c.context_feature == context_features.c.name))
                .where(configurable.c.setting == name)
                .order_by(context_features.c.index))
                                 ).scalars().all()

        # we query both the rule and its configurable features at the same time. Meaning that if the rule does not
        # exist, we make 1 too many calls. However, we expect to make so few get_setting calls to non-existent rules
        # that this is negligible
        if data_row is None:
            return None

        type_ = setting_type(data_row['type'])
        metadata_ = orjson.loads(data_row['metadata'])
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
                    metadata=str(orjson.dumps(setting.metadata), 'utf-8')
                )
            )
            await conn.execute(
                configurable.insert().values(
                    [{'setting': setting.name, 'context_feature': cf} for cf in setting.configurable_features]
                )
            )

    async def update_setting(self, name: str, changed: Mapping[str, Any], new_contexts: Iterable[str]):
        """
        Edit an existing setting in the DB
        Args:
            name: The name of the setting to edit
            changed: The fields of the setting to change
            new_contexts: An iterable of new context names to assign to the setting as configurable
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

    async def get_settings(self, full_data) -> List[SettingSpec]:
        """
        Returns:
            A list of all setting names in the DB
        """
        select_query = select([settings.c.name]).order_by(settings.c.name)
        if full_data:
            select_query.append_column(settings.c.type)
            select_query.append_column(settings.c.default_value)
            select_query.append_column(settings.c.metadata)

        if full_data:
            async with self.db_engine.connect() as conn:
                records = (await conn.execute(select_query)).mappings().all()
                configurable_rows = (await conn.execute(
                    select([configurable.c.setting, configurable.c.context_feature])
                    .select_from(join(configurable, context_features,
                                      configurable.c.context_feature == context_features.c.name))
                    .order_by(configurable.c.setting, context_features.c.index)
                )).mappings().all()

            configurables = {
                setting: [row['context_feature'] for row in rows]
                for (setting, rows) in groupby(configurable_rows, key=itemgetter('setting'))
            }
        else:
            async with self.db_engine.connect() as conn:
                records = (await conn.execute(select_query)).mappings().all()
            configurables = {}

        return [
            SettingSpec(
                row['name'],
                row['type'] if full_data else None,
                orjson.loads(row['default_value']) if full_data else None,
                orjson.loads(row['metadata']) if full_data else None,
                configurables[row['name']] if full_data else None
            ) for row in records
        ]
