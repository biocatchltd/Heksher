import asyncio
from unittest.mock import AsyncMock

from async_asgi_testclient import TestClient
from pytest import fixture

import heksher.app as app_mod
from heksher.main import app


class MockEngine:
    def __init__(self):
        self.connection = DBConnectionMock()

    def connect(self):
        return self.connection

    def begin(self):
        return self.connection

    async def dispose(self):
        pass

    def __call__(self, *args, **kwargs):
        return self


class DBConnectionMock:
    def __init__(self):
        self.execute = AsyncMock()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@fixture
def mock_engine():
    ret = MockEngine()
    return ret


@fixture
async def app_client(monkeypatch, mock_engine):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', 'postgresql://dbuser:swordfish@pghost10/')

    monkeypatch.setattr(app_mod, 'create_async_engine', mock_engine)

    async with TestClient(app) as app_client:
        yield app_client


@fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
