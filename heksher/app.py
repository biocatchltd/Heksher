import re
from asyncio import wait_for
from logging import getLogger, INFO

import sentry_sdk
from aiologstash import create_tcp_handler
from databases import Database
from envolved import EnvVar, Schema
from envolved.parsers import CollectionParser
from fastapi import FastAPI

from heksher._version import __version__
from heksher.db_logic import DBLogic

logger = getLogger(__name__)

connection_string = EnvVar('HEKSHER_DB_CONNECTION_STRING', type=str)
startup_context_features = EnvVar('HEKSHER_STARTUP_CONTEXT_FEATURES', type=CollectionParser(';', str))


class LogstashSettingSchema(Schema):
    # todo remove explicit uppercase names when envolved is upgraded
    host: str = EnvVar('HOST')
    port: int = EnvVar('PORT')
    level: int = EnvVar('LEVEL', default=INFO)
    tags = EnvVar('TAGS', type=CollectionParser.pair_wise_delimited(re.compile(r'\s'), ':', str, str), default={})


logstash_settings_ev = EnvVar('HEKSHER_LOGSTASH_', default=None, type=LogstashSettingSchema)
sentry_dsn_ev = EnvVar('SENTRY_DSN', default='', type=str)


class HeksherApp(FastAPI):
    """
    The application class
    """
    db: Database
    db_logic: DBLogic

    async def startup(self):
        logstash_settings = logstash_settings_ev.get()
        if logstash_settings is not None:
            handler = await create_tcp_handler(logstash_settings.host, logstash_settings.port, extra={
                'heksher_version': __version__,
                **logstash_settings.tags
            })
            getLogger('heksher').addHandler(handler)
            getLogger('heksher').setLevel(logstash_settings.level)

        db_connection_string = connection_string.get()

        self.db = Database(db_connection_string)
        await self.db.connect()
        self.db_logic = DBLogic(self.db)

        # assert that the db logic holds up
        expected_context_features = startup_context_features.get()
        await self.db_logic.ensure_context_features(expected_context_features)

        sentry_dsn = sentry_dsn_ev.get()
        if sentry_dsn:
            try:
                sentry_sdk.init(sentry_dsn, release=f"Heksher@{__version__}")
            except Exception:
                logger.exception("cannot start sentry")

    async def shutdown(self):
        await wait_for(self.db.disconnect(), timeout=10)

    async def is_healthy(self):
        try:
            db_version = await self.db.fetch_one("SHOW SERVER_VERSION;")
        except Exception:
            db_version = None

        return bool(db_version)
