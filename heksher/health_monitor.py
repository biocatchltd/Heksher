from __future__ import annotations

from asyncio import CancelledError, Task, create_task, sleep
from logging import getLogger
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

_logger = getLogger(__name__)


class HealthMonitor:
    """
    Checks the connection to PostgreSQL periodically, sending logs whenever connection failed
    """

    status: bool
    _engine: AsyncEngine
    _monitor_task: Optional[Task] = None

    async def _psql_health_callback(self) -> None:
        async with self._engine.connect() as conn:
            db_version = (await conn.execute(text('''SHOW SERVER_VERSION'''))).scalar_one_or_none()
        if db_version is None:
            raise ValueError("expected version, got None")

    async def _check(self) -> bool:
        try:
            await self._psql_health_callback()
            _logger.debug("PostgreSQL is healthy")
            return True
        except Exception:
            _logger.exception("PostgreSQL health check failed")
            return False

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
                self.status = await self._check()
                await sleep(interval)

        self.status = await self._check()
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
