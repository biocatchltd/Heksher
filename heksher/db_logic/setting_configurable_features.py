from typing import List

from heksher.db_logic.metadata import configurable, settings
from sqlalchemy.ext.asyncio import AsyncConnection


async def set_settings_configurable_features(conn: AsyncConnection, setting_name: str, configurable_features: List[str],
                                             version: str):
    await conn.execute(configurable.delete().where(configurable.c.setting_name == setting_name))
    await conn.execute(configurable.insert().values([
        {'setting': setting_name, 'context_feature': cf} for cf in configurable_features]))
    await conn.execute(settings.update().values({'version': version}).where(settings.c.name == setting_name))

