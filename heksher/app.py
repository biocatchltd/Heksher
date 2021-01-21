import re
from asyncio import wait_for
from logging import getLogger, INFO

from aiologstash import create_tcp_handler
from databases import Database
from envolved import EnvVar, Schema
from envolved.parsers import CollectionParser
from fastapi import FastAPI

from heksher._version import __version__
from heksher.db_logic import DBLogic

connection_string = EnvVar('HEKSHER_DB_CONNECTION_STRING', type=str)
startup_context_features = EnvVar('HEKSHER_STARTUP_CONTEXT_FEATURES', type=CollectionParser(';', str))


class LogstashSettingSchema(Schema):
    host: str = EnvVar()
    port: int = EnvVar()
    level: int = EnvVar(default=INFO)
    tags = EnvVar(type=CollectionParser.pair_wise_delimited(re.compile(r'\s'), ':', str, str))


logstash_settings = EnvVar('HEKSHER_LOGSTASH_', default=None, type=LogstashSettingSchema)


class HeksherApp(FastAPI):
    """
    The application class
    """
    db: Database
    db_logic: DBLogic

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    async def startup(self):
        settings = logstash_settings.get()
        if settings is not None:
            handler = await create_tcp_handler(settings.host, settings.port, extra={
                'heksher_version': __version__,
                **settings.tags
            })
            getLogger('heksher').addHandler(handler)
            getLogger('heksher').setLevel(settings.level)

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
