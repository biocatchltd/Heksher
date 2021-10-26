from __future__ import annotations

import traceback
from asyncio import CancelledError, Task, create_task, sleep
from dataclasses import InitVar, dataclass, field
from enum import Enum, auto
from io import StringIO
from logging import Logger, getLogger
from typing import Any, Dict, Optional, Union

from fastapi import APIRouter, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.responses import PlainTextResponse
from starlette.status import HTTP_200_OK, HTTP_500_INTERNAL_SERVER_ERROR

_logger = getLogger(__name__)


class HealthStatus(Enum):
    Healthy = auto()
    Failed = auto()

    def http_status_code(self) -> int:
        """
        Get the appropriate HTTP status code for the health status
        """
        if self is self.Healthy:
            return HTTP_200_OK
        return HTTP_500_INTERNAL_SERVER_ERROR


class HealthMonitor:

    def __init__(self, *, extra: Optional[Dict[str, Any]] = None):
        self._status: Optional[PostgreSQLHealth] = None
        self._monitor_task: Optional[Task] = None
        self._engine: Optional[AsyncEngine] = None
        self._const_extra = extra or {}

    async def _psql_health_callback(self) -> PostgreSQLHealth:
        async with self._engine.connect() as conn:
            db_version = await conn.execute(text('''SHOW SERVER_VERSION'''))
            db_version = db_version.scalar_one_or_none()
        if not db_version:
            return PostgreSQLHealth(
                HealthStatus.Failed, {"db_version": None}
            )
        return PostgreSQLHealth(HealthStatus.Healthy, {'db_version': str(db_version)})

    async def _check(self) -> PostgreSQLHealth:
        extra = dict(self._const_extra) or {}
        try:
            ret: PostgreSQLHealth = await self._psql_health_callback()
        except Exception as ex:
            return PostgreSQLHealth(HealthStatus.Failed, extra, exception=ex)
        else:
            if isinstance(ret, PostgreSQLHealth):
                if ret.extra:
                    extra.update(ret.extra)
                ret.extra = extra
                return ret
            else:
                return PostgreSQLHealth(HealthStatus.Failed, extra)

    async def _set_status(self) -> None:
        self._status = await self._check()
        self._status.log(_logger)

    async def start(self, engine: AsyncEngine, interval: float = 5.0) -> None:
        """
        Create a monitor task that runs every interval seconds.
        Args:
            engine: async engine of postgresql
            interval: The interval between runs.
        """
        if self._monitor_task:
            raise RuntimeError('monitor task already running')

        self._engine = engine

        async def loop_task() -> None:
            while True:
                await self._set_status()
                await sleep(interval)

        await self._set_status()
        self._monitor_task = create_task(loop_task())

    async def stop(self) -> None:
        """
        Stop the monitor task
        """
        if not self._monitor_task:
            return
        self._monitor_task.cancel()
        try:
            await self._monitor_task
        except CancelledError:
            pass
        finally:
            self._monitor_task = None

    def add_fastapi_route(self, router: Union[APIRouter, FastAPI], *,
                          path: str = "/api/health") -> None:
        """
        Register a fastapi route to an application or router, responding with a truncated healthcheck schema
        Args:
            router: The fastapi router or app to add the route to
            path: The route path
        """

        async def endpoint() -> PlainTextResponse:
            health = self._status
            version = health.extra.get('version', '')
            status_code = health.status.http_status_code()

            return PlainTextResponse(
                content=version,
                status_code=status_code
            )

        router.add_api_route(
            path=path,
            endpoint=endpoint,
            methods=['GET'],
            responses={
                HTTP_200_OK: {'description': 'the service is fully operational'},
                HTTP_500_INTERNAL_SERVER_ERROR: {'description': 'the service is in a failed state'},
            },
            name="health_check",
        )


@dataclass
class PostgreSQLHealth:
    """
    An object indicating the health status of PostgreSQL
    """
    status: Optional[HealthStatus]
    extra: Dict[str, Any] = field(default_factory=dict)

    exception: InitVar[Optional[BaseException]] = None
    """if set, its info will automatically will be added to the extra"""

    def __post_init__(self, exception: Optional[BaseException]):
        if exception and 'exc_text' not in self.extra:
            with StringIO() as sio:
                traceback.print_exception(type(exception), exception, exception.__traceback__, None, sio)
                s = sio.getvalue()
            self.extra['exc_text'] = s.rstrip()

    def log(self, logger: Logger) -> None:
        """
        log a message if the dependency is failed
        Args:
            logger: the logger to use
        """
        if self.status is HealthStatus.Failed:
            extra = {
                'dependency_extra': self.extra
            }
            logger.error("PostgreSQL is in failed health", extra=extra)
