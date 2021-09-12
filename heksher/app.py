import re
from asyncio import wait_for
from logging import INFO, getLogger

import orjson
import sentry_sdk
from aiologstash import create_tcp_handler
from envolved import EnvVar, Schema
from envolved.parsers import CollectionParser
from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from heksher._version import __version__
from heksher.db_logic import DBLogic
from heksher.util import db_url_with_async_driver

logger = getLogger(__name__)

connection_string = EnvVar('HEKSHER_DB_CONNECTION_STRING', type=db_url_with_async_driver)
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
    engine: AsyncEngine
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

        self.engine = create_async_engine(db_connection_string,
                                          json_serializer=lambda obj: orjson.dumps(obj).decode(),
                                          json_deserializer=orjson.loads
                                          )
        self.db_logic = DBLogic(self.engine)

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
        await wait_for(self.engine.dispose(), timeout=10)

    async def is_healthy(self):
        try:
            async with self.engine.connect() as conn:
                db_version = (await conn.execute(text('''SHOW SERVER_VERSION'''))).scalar_one_or_none()
        except Exception as e:
            print(e)
            db_version = None

        return bool(db_version)
