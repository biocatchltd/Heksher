import asyncio
import json
import sys
from subprocess import run

from async_asgi_testclient import TestClient
from pytest import fixture
from yellowbox.extras.postgresql import PostgreSQLService

from heksher.main import app


@fixture(scope='session')
def sql_service(docker_client):
    service: PostgreSQLService
    with PostgreSQLService.run(docker_client) as service:
        yield service


@fixture
def purge_sql(sql_service):
    with sql_service.connection() as connection:
        connection.execute(f'''
        DROP SCHEMA public CASCADE;
        CREATE SCHEMA public;
        GRANT ALL ON SCHEMA public TO {sql_service.user};
        GRANT ALL ON SCHEMA public TO public;
        ''')
    # we run create_all from outside to avoid alembic's side effects
    run([sys.executable, 'alembic/from_scratch.py', sql_service.local_connection_string()], check=True)
    yield


@fixture
async def app_client(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    async with TestClient(app) as app_client:
        yield app_client


@fixture
async def size_limit_setting(app_client):
    res = await app_client.put('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {
        'created': True,
        'changed': [],
        'incomplete': {}
    }


@fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
