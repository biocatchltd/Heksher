from unittest.mock import AsyncMock

from pytest import fixture
from starlette.testclient import TestClient

import heksher.app as app_mod
from heksher.db_logic import DBLogic
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
def app_client(monkeypatch, mock_engine):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', 'postgresql://dbuser:swordfish@pghost10/')
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["A","B","C"]')

    monkeypatch.setattr(app_mod, 'create_async_engine', mock_engine)
    monkeypatch.setattr(app_mod, 'DBLogic', lambda *a: AsyncMock(DBLogic))

    with TestClient(app) as app_client:
        yield app_client
