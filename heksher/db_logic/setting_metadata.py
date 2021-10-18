from typing import Any, Dict

from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert

from heksher.db_logic.logic_base import DBLogicBase
from heksher.db_logic.metadata import setting_metadata


class SettingMetadataMixin(DBLogicBase):

    async def update_setting_metadata(self, name: str, metadata: Dict[str, Any]):
        """
        Update the metadata of the given setting. Similar to the dict.update() method, meaning that for existing keys,
        the value will be updated, and new keys will be added as well.
        Args:
            name: the name of the setting to update it's metadata.
            metadata: the metadata to update.
        """
        async with self.db_engine.begin() as conn:
            stmt = insert(setting_metadata).values(
                [{'setting': name, 'key': k, 'value': v} for (k, v) in metadata.items()]
            )
            await conn.execute(stmt.on_conflict_do_update(index_elements=[setting_metadata.c.setting,
                                                                          setting_metadata.c.key],
                                                          set_={"value": stmt.excluded.value}))

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
            await conn.execute(insert(setting_metadata)
                               .values([{'setting': name, 'key': key, 'value': new_value}])
                               .on_conflict_do_update(index_elements=[setting_metadata.c.setting,
                                                                      setting_metadata.c.key],
                                                      set_={"value": new_value}))

    async def delete_setting_metadata(self, name: str):
        """
        Remove a setting's metadata from the DB
        Args:
            name: the name of the setting to remove its metadata
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(setting_metadata.delete().where(setting_metadata.c.setting == name))

    async def delete_setting_metadata_key(self, name: str, key: str):
        """
        Remove a specific key from the setting's metadata
        Args:
            name: the name of the setting
            key: the name of the key to be deleted from the setting metadata
        """
        async with self.db_engine.begin() as conn:
            await conn.execute(setting_metadata.delete()
                               .where(and_(setting_metadata.c.setting == name,
                                           setting_metadata.c.key == key)))
