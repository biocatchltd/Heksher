from dataclasses import dataclass
from functools import cached_property
from itertools import groupby
from typing import Any, Dict, Iterable, List, Optional

import orjson
from _operator import itemgetter
from sqlalchemy import String, column, delete, join, or_, select, values
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncConnection

from heksher.db_logic.metadata import configurable, context_features, setting_aliases, setting_metadata, settings
from heksher.setting_types import SettingType, setting_type


@dataclass
class SettingSpec:
    name: str
    raw_type: Optional[str]
    raw_default_value: Any
    metadata: Optional[Dict[str, Any]]
    configurable_features: Optional[List[str]]
    aliases: Optional[List[str]]
    version: str

    @cached_property
    def type(self) -> SettingType:
        return setting_type(self.raw_type)

    @cached_property
    def default_value(self):
        return orjson.loads(self.raw_default_value)


async def db_get_canonical_names(conn: AsyncConnection, names_or_aliases: Iterable[str]) -> Dict[str, str]:
    """
    Args:
        conn: the database connection
        names_or_aliases: an iterable of potential setting names/aliases.

    Returns:
        A dictionary of the given names/aliases to their canonical names.
        Note: For settings that do no exist, the canonical name will be None.
    """
    names_table = values(column('n', String), name='names').data([(name,) for name in names_or_aliases])

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


async def db_get_setting(conn: AsyncConnection, name_or_alias: str, *, include_metadata: bool, include_aliases: bool,
                         include_configurable_features: bool) -> Optional[SettingSpec]:
    stmt = (
        select([settings.c.name, settings.c.type, settings.c.default_value, settings.c.version])
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
    if include_aliases:
        stmt = (
            select([setting_aliases.c.alias])
            .select_from(
                join(settings, setting_aliases, settings.c.name == setting_aliases.c.setting)
            )
            .where(settings.c.name == setting_name)
            .order_by(setting_aliases.c.alias)
        )
        aliases = (await conn.execute(stmt)).scalars().all()
    else:
        aliases = None

    if include_configurable_features:
        stmt = (
            select([configurable.c.context_feature])
            .select_from(
                join(configurable, context_features, configurable.c.context_feature == context_features.c.name)
            )
            .where(configurable.c.setting == setting_name)
            .order_by(context_features.c.index)
        )
        configurable_features = (await conn.execute(stmt)).scalars().all()
    else:
        configurable_features = None

    if include_metadata:
        stmt = (
            select([setting_metadata.c.key, setting_metadata.c.value])
            .where(setting_metadata.c.setting == setting_name)
        )
        metadata_ = dict((await conn.execute(stmt)).all())
    else:
        metadata_ = None

    return SettingSpec(
        setting_name,
        data_row['type'],
        data_row['default_value'],
        metadata_,
        configurable_features,
        aliases,
        data_row['version']
    )


async def db_add_setting(conn: AsyncConnection, setting: SettingSpec):
    await conn.execute(
        settings.insert().values(
            name=setting.name,
            type=str(setting.type),
            default_value=str(orjson.dumps(setting.default_value), 'utf-8'),
            version=setting.version
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
    assert not setting.aliases  # newly added settings can't have aliases


async def db_update_setting(conn: AsyncConnection, old_name: str, new_name: Optional[str],
                            configurable_features: Optional[List[str]], type: Optional[SettingType],
                            default_value: Optional[Any], metadata: Optional[Dict[str, Any]], version: str):
    if configurable_features is not None:
        await conn.execute(
            configurable.delete().where(configurable.c.setting == old_name)
        )
        await conn.execute(
            configurable.insert().values(
                [{'setting': old_name, 'context_feature': cf} for cf in configurable_features]
            )
        )
    if metadata is not None:
        await conn.execute(
            setting_metadata.delete().where(setting_metadata.c.setting == old_name)
        )
        await conn.execute(
            setting_metadata.insert().values(
                [{'setting': old_name, 'key': k, 'value': v} for (k, v) in metadata.items()]
            )
        )

    # we change the row last, so that the other tables can still refer to the setting by it's old name
    row_changes = {'version': version}
    if new_name:
        row_changes['name'] = new_name
    if type:
        row_changes['type'] = str(type)
    if default_value:
        row_changes['default_value'] = str(orjson.dumps(default_value), 'utf-8')
    await conn.execute(
        settings.update().where(settings.c.name == old_name).values(**row_changes)
    )

    if new_name:
        # remove the new name from the aliases table, if it exists
        await conn.execute(
            setting_aliases.delete().where(setting_aliases.c.alias == new_name)
        )
        await conn.execute(
            insert(setting_aliases).values(
                [{'setting': new_name, 'alias': old_name}]
            )
        )


async def db_delete_setting(conn: AsyncConnection, name: str) -> bool:
    """
    Remove a setting from the DB
    Returns:
        Whether a setting with the name was found
    """
    resp = (await conn.execute(settings.delete().where(settings.c.name == name))).rowcount
    return resp == 1


async def db_get_settings(conn: AsyncConnection, include_configurable_features: bool, include_metadata: bool,
                          include_aliases: bool, setting_names: Optional[Iterable[str]] = None)\
        -> Dict[str, SettingSpec]:
    """
    Returns:
        A list of all setting specs in the DB
    """
    select_query = select([settings.c.name, settings.c.type, settings.c.default_value, settings.c.version]) \
        .order_by(settings.c.name)

    if setting_names:
        select_query = select_query.where(settings.c.name.in_(setting_names))

    records = (await conn.execute(select_query)).all()
    if include_configurable_features:
        configurable_rows = (await conn.execute(
            select([configurable.c.setting, configurable.c.context_feature])
            .select_from(join(configurable, context_features,
                              configurable.c.context_feature == context_features.c.name))
            .order_by(configurable.c.setting, context_features.c.index)
        )).mappings().all()
    else:
        configurable_rows = None
    if include_metadata:
        metadata_rows = await conn.execute(
            setting_metadata.select().order_by(setting_metadata.c.setting)
        )
    else:
        metadata_rows = None
    if include_aliases:
        alias_rows = await conn.execute(
            setting_aliases.select().order_by(setting_aliases.c.setting)
        )
    else:
        alias_rows = None

    if include_configurable_features:
        configurable_features = {
            setting: [row['context_feature'] for row in rows]
            for (setting, rows) in groupby(configurable_rows, key=itemgetter('setting'))
        }
    else:
        configurable_features = None
    if include_metadata:
        metadata = {
            setting: {k: v for (_, k, v) in rows} for (setting, rows) in groupby(metadata_rows, key=itemgetter(0))
        }
    else:
        metadata = None
    if include_aliases:
        aliases = {
            setting: [v for (_, v) in rows] for (setting, rows) in groupby(alias_rows, key=itemgetter(0))
        }
    else:
        aliases = None

    return {
        name: SettingSpec(
            name,
            raw_type,
            default_value,
            metadata.get(name, {}) if include_metadata else None,
            configurable_features[name] if include_configurable_features else None,
            aliases.get(name, []) if include_aliases else None,
            version
        ) for (name, raw_type, default_value, version) in records
    }


async def db_set_setting_type(conn: AsyncConnection, setting_name: str, new_type: SettingType, new_version: str):
    """
    Change the type of a setting. Does not check validity.
    """
    await conn.execute(settings.update().where(settings.c.name == setting_name)
                       .values(type=str(new_type), version=new_version))


async def db_rename_setting(conn: AsyncConnection, old_name: str, new_name: str, new_version: str):
    # this should cascade through all other tables
    await conn.execute(
        settings.update()
        .where(settings.c.name == old_name)
        .values({"name": new_name, 'version': new_version})
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


async def db_bump_setting_version(conn: AsyncConnection, setting_name: str, new_version: str):
    await conn.execute(settings.update().where(settings.c.name == setting_name).values(version=new_version))
