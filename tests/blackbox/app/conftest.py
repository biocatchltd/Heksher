import asyncio
import json

from async_asgi_testclient import TestClient
from pytest import fixture
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from heksher.db_logic.metadata import context_features
from heksher.main import app


@fixture
async def check_indexes_of_cf(sql_service):
    yield
    sql_connection_string = sql_service.local_connection_string(driver="asyncpg")
    engine = create_async_engine(sql_connection_string)
    async with engine.begin() as conn:
        rows = (await conn.execute(select(context_features.c.index)
                                   .order_by(context_features.c.index))).scalars().all()
    assert rows == list(range(len(rows)))


@fixture
async def app_client(monkeypatch, sql_service, purge_sql, check_indexes_of_cf):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    async with TestClient(app) as app_client:
        yield app_client


@fixture
async def size_limit_setting(app_client):
    res = await app_client.post('/api/v1/settings/declare', data=json.dumps({
        'name': 'size_limit',
        'configurable_features': ['user', 'theme'],
        'type': 'int',
        'default_value': 200,
        'metadata': {'testing': True}
    }))
    res.raise_for_status()
    assert res.json() == {'outcome': 'created'}


@fixture
async def example_rule(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright'},
        'value': 10,
        'metadata': {'test': True}
    }))
    res.raise_for_status()
    j_result = res.json()
    rule_id = j_result.pop('rule_id')
    assert not j_result

    return rule_id


@fixture
async def example_rule2(size_limit_setting, app_client):
    res = await app_client.post('/api/v1/rules', data=json.dumps({
        'setting': 'size_limit',
        'feature_values': {'theme': 'bright', 'user': 'me'},
        'value': 10,
        'metadata': {'test': True}
    }))
    res.raise_for_status()
    j_result = res.json()
    rule_id = j_result.pop('rule_id')
    assert not j_result

    return rule_id


@fixture(scope='session')
def event_loop(request):
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()
