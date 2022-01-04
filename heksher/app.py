import re
from asyncio import wait_for
from logging import INFO, getLogger
from typing import Sequence

import orjson
import sentry_sdk
from aiologstash import create_tcp_handler
from envolved import EnvVar, Schema
from envolved.parsers import CollectionParser
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from heksher._version import __version__
from heksher.db_logic.context_feature import db_add_context_features, db_get_context_features, db_move_context_features
from heksher.db_logic.util import supersequence_new_elements
from heksher.health_monitor import HealthMonitor
from heksher.util import db_url_with_async_driver

logger = getLogger(__name__)

connection_string = EnvVar('HEKSHER_DB_CONNECTION_STRING', type=db_url_with_async_driver)
startup_context_features = EnvVar('HEKSHER_STARTUP_CONTEXT_FEATURES', type=CollectionParser(';', str), default=None)


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
    health_monitor: HealthMonitor

    async def ensure_context_features(self, expected_context_features: Sequence[str]):
        async with self.engine.connect() as conn:
            existing_features = await db_get_context_features(conn)
        actual = dict(existing_features)
        super_sequence = supersequence_new_elements(expected_context_features, actual)
        if super_sequence is None:
            raise RuntimeError(f'expected context features to be a subsequence of {expected_context_features}, '
                               f'actual: {actual}')
        expected = {cf: i for (i, cf) in enumerate(expected_context_features)}
        misplaced_keys = [k for k, v in actual.items() if expected[k] != v]
        if misplaced_keys:
            logger.warning('fixing indexing for context features', extra={'misplaced_keys': misplaced_keys})
            async with self.engine.begin() as conn:
                await db_move_context_features(conn, expected)
        if super_sequence:
            logger.info('adding new context features', extra={
                'new_context_features': [element for (element, _) in super_sequence]
            })
            async with self.engine.begin() as conn:
                await db_add_context_features(conn, dict(super_sequence))

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
                                          json_deserializer=orjson.loads,
                                          )

        # assert that the db logic holds up
        expected_context_features = startup_context_features.get()
        if expected_context_features is not None:
            await self.ensure_context_features(expected_context_features)

        self.health_monitor = HealthMonitor(self.engine)
        await self.health_monitor.start()

        sentry_dsn = sentry_dsn_ev.get()
        if sentry_dsn:
            try:
                sentry_sdk.init(sentry_dsn, release=f"Heksher@{__version__}")
            except Exception:
                logger.exception("cannot start sentry")

    async def shutdown(self):
        await self.health_monitor.stop()
        await wait_for(self.engine.dispose(), timeout=10)
