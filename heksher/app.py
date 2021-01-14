from asyncio import wait_for

from databases import Database
from envolved import EnvVar
from envolved.parsers import CollectionParser
from fastapi import FastAPI

from heksher.db_logic import DBLogic

connection_string = EnvVar('HEKSHER_DB_CONNECTION_STRING', type=str)
startup_context_features = EnvVar('HEKSHER_STARTUP_CONTEXT_FEATURES', type=CollectionParser(';', str))


class HeksherApp(FastAPI):
    """
    The application class
    """
    db: Database
    db_logic: DBLogic

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def startup(self):
        db_connection_string = connection_string.get()
        self.db = Database(db_connection_string)
        await self.db.connect()

        self.db_logic = DBLogic(self.db)

        # assert that the db logic holds up
        expected_context_features = startup_context_features.get()
        await self.db_logic.ensure_context_features(expected_context_features)

    async def shutdown(self):
        await wait_for(self.db.disconnect(), timeout=10)

    async def is_healthy(self):
        try:
            db_version = await self.db.fetch_one("SHOW SERVER_VERSION;")
        except Exception:
            db_version = None

        return bool(db_version)
