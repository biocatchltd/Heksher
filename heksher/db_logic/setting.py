from itertools import groupby
from typing import Any, Dict, Iterable, List, Mapping, NamedTuple, Optional

import orjson
from _operator import itemgetter
from sqlalchemy import String, column, delete, join, or_, select, values
from sqlalchemy.dialects.postgresql import insert

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import configurable, context_features, setting_aliases, setting_metadata, settings
from heksher.setting import Setting
from heksher.setting_types import SettingType, setting_type


class SettingSpec(NamedTuple):
    name: str
    raw_type: Optional[str]
    default_value: Optional[Any]
    metadata: Optional[Dict[str, Any]]
    configurable_features: Optional[List[str]]
    aliases: List[str]


class SettingMixin(DBLogicBase):
    async def get_canonical_names(self, names_or_aliases: Iterable[str]) -> Dict[str, str]:
        """
        Args:
            names_or_aliases: an iterable of potential setting names/aliases.

        Returns:
            A dictionary of the given names/aliases to their canonical names.
            Note: For settings that do no exist, the canonical name will be None.
        """
        names_table = values(column('n', String), name='names').data([(name,) for name in names_or_aliases])

        async with self.db_engine.connect() as conn:
            stmt = (
                select([names_table.c.n, settings.c.name])
                .select_from(
                    join(names_table,
                         join(settings,
                              setting_aliases,
                              settings.c.name == setting_aliases.c.setting,
                              isouter=True),
                         or_(settings.c.name == names_table.c.n, setting_aliases.c.alias == names_table.c.n),
                         isouter=True)
                )
                .distinct()
            )
            results = (await conn.execute(stmt)).all()
        return dict(results)

    async def get_setting(self, name_or_alias: str, *, include_metadata: bool) -> Optional[Setting]:
        """
        Args:
            name_or_alias: The name/alias of a setting
            include_metadata: whether to include setting metadata
        Returns:
            The setting object for the setting in the DB with the same name, or None if it does not exist

        """
        async with self.db_engine.connect() as conn:
            stmt = (
                select([settings.c.name, settings.c.type, settings.c.default_value])
                .select_from(
                    join(settings, setting_aliases, settings.c.name == setting_aliases.c.setting, isouter=True)
                )
                .where(or_(settings.c.name == name_or_alias, setting_aliases.c.alias == name_or_alias))
                .limit(1)
            )
            data_row = (await conn.execute(stmt)).mappings().first()

            if data_row is None:
                return None

            setting_name = data_row['name']

            stmt = (
                select([configurable.c.context_feature])
                .select_from(
                    join(configurable, context_features, configurable.c.context_feature == context_features.c.name)
                )
                .where(configurable.c.setting == setting_name)
                .order_by(context_features.c.index)
            )
            configurable_rows = (await conn.execute(stmt)).scalars().all()

            if include_metadata:
                stmt = (
                    select([setting_metadata.c.key, setting_metadata.c.value])
                    .where(setting_metadata.c.setting == setting_name)
                )
                metadata_ = dict((await conn.execute(stmt)).all())
            else:
                metadata_ = None

        type_ = setting_type(data_row['type'])
        default_value_ = orjson.loads(data_row['default_value'])
        return Setting(
            setting_name,
            type_,
            default_value_,
            configurable_rows,
            metadata_
        )

    async def add_setting(self, setting: Setting, alias: Optional[str] = None):
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
            if alias:
                await conn.execute(
                    insert(setting_aliases).values(
                        [{'setting': setting.name, 'alias': alias}]
                    )
                )

    async def update_setting(self, name: str, changed: Mapping[str, Any], new_contexts: Iterable[str],
                             new_metadata: Optional[Dict[str, Any]], alias: Optional[str]):
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
            if alias:
                await conn.execute(
                    insert(setting_aliases).values(
                        [{'setting': name, 'alias': alias}]
                    ).on_conflict_do_nothing()
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

    async def get_setting_full(self, name_or_alias: str) -> Optional[SettingSpec]:
        """
        Args:
            name_or_alias: The name/alias of a setting
        Returns:
            The setting specs object for the setting in the DB with the same name, or None if it does not exist
        """
        setting = await self.get_setting(name_or_alias, include_metadata=True)

        if not setting:
            return None

        async with self.db_engine.connect() as conn:
            alias_rows = (await conn.execute(
                select([setting_aliases.c.alias])
                .where(setting_aliases.c.setting == setting.name)
            )).scalars().all()

        return SettingSpec(
            setting.name,
            str(setting.type),
            setting.default_value,
            setting.metadata,
            list(setting.configurable_features),
            list(alias_rows)
        )

    async def get_all_settings_full(self) -> List[SettingSpec]:
        """
        Returns:
            A list of all setting specs in the DB
        """
        select_query = select([settings.c.name, settings.c.type, settings.c.default_value]).order_by(settings.c.name)

        async with self.db_engine.connect() as conn:
            records = (await conn.execute(select_query)).mappings().all()
            configurable_rows = (await conn.execute(
                select([configurable.c.setting, configurable.c.context_feature])
                .select_from(join(configurable, context_features,
                                  configurable.c.context_feature == context_features.c.name))
                .order_by(configurable.c.setting, context_features.c.index)
            )).mappings().all()
            metadata_rows = await conn.execute(
                setting_metadata.select().order_by(setting_metadata.c.setting)
            )
            alias_rows = await conn.execute(
                setting_aliases.select().order_by(setting_aliases.c.setting)
            )

        configurables = {
            setting: [row['context_feature'] for row in rows]
            for (setting, rows) in groupby(configurable_rows, key=itemgetter('setting'))
        }
        metadata = {
            setting: {k: v for (_, k, v) in rows} for (setting, rows) in groupby(metadata_rows, key=itemgetter(0))
        }
        aliases = {
            setting: [v for (_, v) in rows] for (setting, rows) in groupby(alias_rows, key=itemgetter(0))
        }

        return [
            SettingSpec(
                row['name'],
                row['type'],
                orjson.loads(row['default_value']),
                metadata.get(row['name'], {}),
                configurables[row['name']],
                aliases.get(row['name'], []),
            ) for row in records
        ]

    async def get_all_settings_names(self) -> List[str]:
        """
        Returns:
            A list of all setting names in the DB
        """
        select_query = select([settings.c.name]).order_by(settings.c.name)

        async with self.db_engine.connect() as conn:
            return list((await conn.execute(select_query)).scalars().all())

    async def set_setting_type(self, setting_name: str, new_type: SettingType):
        """
        Change the type of a setting. Does not check validity.
        Args:
            setting_name: the name of the setting
            new_type: the new type of the setting
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(settings.update().where(settings.c.name == setting_name).values(type=str(new_type)))

    async def rename_setting(self, old_name: str, new_name: str):
        """
        Change a canonical setting name to another one, adding the old one as an alias
        Args:
            old_name: The name of the setting to rename
            new_name: The new name to set for the setting
        """
        async with self.db_engine.begin() as conn:
            # this should cascade through all other tables
            await conn.execute(
                settings.update()
                .where(settings.c.name == old_name)
                .values({"name": new_name})
            )
            # add the old name as an alias of the new one
            await conn.execute(
                insert(setting_aliases).values(
                    [{'setting': new_name, 'alias': old_name}]
                )
            )
            # in case that the new name is an old alias, we remove the old alias from the aliases table
            await conn.execute(
                delete(setting_aliases)
                .where(setting_aliases.c.setting == new_name, setting_aliases.c.alias == new_name)
            )
