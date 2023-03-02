import re
from asyncio import wait_for
from dataclasses import dataclass
from logging import INFO, getLogger
from typing import Dict, Sequence

import orjson
import sentry_sdk
from aiologstash2 import create_tcp_handler
from envolved import env_var
from envolved.parsers import CollectionParser
from fastapi import FastAPI, Request
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from starlette.responses import PlainTextResponse
from starlette.status import HTTP_404_NOT_FOUND

from heksher._version import __version__
from heksher.db_logic.context_feature import db_add_context_features, db_get_context_features, db_move_context_features
from heksher.db_logic.util import supersequence_new_elements
from heksher.health_monitor import HealthMonitor
from heksher.util import db_url_with_async_driver

logger = getLogger('heksher')

connection_string = env_var('HEKSHER_DB_CONNECTION_STRING', type=db_url_with_async_driver)
startup_context_features = env_var('HEKSHER_STARTUP_CONTEXT_FEATURES', type=CollectionParser(';', str), default=None)
doc_only_ev = env_var("DOC_ONLY", type=bool, default=False)


@dataclass
class LogstashSettings:
    host: str
    port: int
    level: int
    tags: dict[str, str]


logstash_settings_ev = env_var('HEKSHER_LOGSTASH_', default=None, type=LogstashSettings, args={
    'host': env_var('HOST'),
    'port': env_var('PORT'),
    'level': env_var('LEVEL', default=INFO),
    'tags': env_var('TAGS', type=CollectionParser.pair_wise_delimited(re.compile(r'\s'), ':', str, str), default={})
})
sentry_dsn_ev = env_var('SENTRY_DSN', default='', type=str)

redoc_mode_whitelist = frozenset((
    '/favicon.ico',
    '/docs',
    '/redoc',
    '/openapi.json',
    '/api/health',
))


class HeksherApp(FastAPI):
    """
    The application class
    """
    engine: AsyncEngine
    health_monitor: HealthMonitor
    doc_only: bool

    async def ensure_context_features(self, expected_context_features: Sequence[str]):
        async with self.engine.begin() as conn:
            existing_features = await db_get_context_features(conn)
        actual: Dict[str, int] = dict(existing_features)  # type: ignore[arg-type]
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
        self.doc_only = doc_only_ev.get()
        if self.doc_only:
            @self.middleware('http')
            async def doc_only_middleware(request: Request, call_next):
                path = request.url.path
                if path.endswith("/"):
                    # our whitelist is without a trailing slash. we remove the slash here and let starlette's redirect
                    # do its work
                    path = path[:-1]
                if path not in redoc_mode_whitelist:
                    return PlainTextResponse("The server is running in doc_only mode, only docs/ and redoc/ paths"
                                             " are supported", HTTP_404_NOT_FOUND)
                return await call_next(request)

            return
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
