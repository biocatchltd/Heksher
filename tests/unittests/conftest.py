from unittest.mock import AsyncMock

from heksher.db_logic import DBLogic
from pytest import fixture
from starlette.testclient import TestClient

import heksher.app as app_mod
from heksher.main import app


class MockDatabaseConnector:
    def __init__(self):
        self.fetch_all = AsyncMock()
        self.fetch_one = AsyncMock()
        self.fetch_val = AsyncMock()
        self.execute = AsyncMock()
        self.execute_many = AsyncMock()

    async def connect(self):
        pass

    async def disconnect(self):
        pass

    def __call__(self, *args, **kwargs):
        return self


@fixture
def mock_database():
    ret = MockDatabaseConnector()
    return ret


@fixture
def app_client(monkeypatch, mock_database):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', 'dummy')
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["A","B","C"]')

    monkeypatch.setattr(app_mod, 'Database', mock_database)
    monkeypatch.setattr(app_mod, 'DBLogic', lambda *a: AsyncMock(DBLogic))

    with TestClient(app) as app_client:
        yield app_client
