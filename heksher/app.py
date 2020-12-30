from asyncio import wait_for
from logging import getLogger
from os import getenv

from databases import Database
from fastapi import FastAPI

from heksher.db_logic import DBLogic


class HeksherApp(FastAPI):
    db: Database
    db_logic: DBLogic

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.logger = getLogger('heksher')

    async def startup(self):
        db_connection_string = getenv('HEKSHER_DB_CONNECTION_STRING')
        if db_connection_string is None:
            raise RuntimeError('HEKSHER_DB_CONNECTION_STRING env var missing')
        self.db = Database(db_connection_string)
        await self.db.connect()

        self.db_logic = DBLogic(self.logger, self.db)

    async def shutdown(self):
        await wait_for(self.db.disconnect(), timeout=10)

    async def is_healthy(self):
        if not self.db.is_connected:
            return False
        return True
