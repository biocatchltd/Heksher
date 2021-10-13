import json

from pytest import fixture, mark
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from heksher.db_logic.metadata import context_features


@fixture
async def check_indexes_of_cf(sql_service):
    yield
    sql_connection_string = sql_service.local_connection_string(driver="asyncpg")
    engine = create_async_engine(sql_connection_string)
    async with engine.connect() as conn:
        rows = (await conn.execute(select([context_features.c.index])
                                   .order_by(context_features.c.index))).scalars().all()
    assert rows == list(range(len(rows)))


@mark.asyncio
async def test_get_all(app_client):
    response = await app_client.get('/api/v1/context_features')
    response.raise_for_status()
    assert response.json() == {
        'context_features': ["user", "trust", "theme"]
    }


@mark.asyncio
async def test_get_context_feature(app_client):
    response = await app_client.get('/api/v1/context_features/trust')
    response.raise_for_status()
    assert response.json() == {'index': 1}


@mark.asyncio
async def test_is_not_context_feature(app_client):
    response = await app_client.get('/api/v1/context_features/not-real')
    assert response.status_code == 404
    assert not response.content


@mark.asyncio
async def test_delete_context_feature(app_client, check_indexes_of_cf):
    response = await app_client.delete('/api/v1/context_features/trust')
    response.raise_for_status()
    context_features = await app_client.get('/api/v1/context_features')
    assert context_features.json() == {
        'context_features': ["user", "theme"]
    }


@mark.asyncio
async def test_delete_context_feature_failed(size_limit_setting, app_client):
    response = await app_client.delete('/api/v1/context_features/user')
    assert response.status_code == 409
    assert response.content == b"context feature can't be deleted, there is at least one setting configured by it"


@mark.asyncio
async def test_patch_after_context_feature(check_indexes_of_cf, app_client):
    response = await app_client.patch('/api/v1/context_features/trust/index', data=json.dumps(
        {"to_after": "theme"}
    ))
    response.raise_for_status()
    context_features = await app_client.get('/api/v1/context_features')
    assert context_features.json() == {
        'context_features': ["user", "theme", "trust"]
    }


@mark.asyncio
async def test_patch_before_context_feature(check_indexes_of_cf, app_client):
    response = await app_client.patch('/api/v1/context_features/trust/index', data=json.dumps(
        {"to_before": "user"}
    ))
    response.raise_for_status()
    context_features = await app_client.get('/api/v1/context_features')
    assert context_features.json() == {
        'context_features': ["trust", "user", "theme"]
    }


@mark.asyncio
async def test_patch_context_feature_doesnt_exists(app_client):
    response = await app_client.patch('/api/v1/context_features/trust/index', data=json.dumps(
        {"to_after": "black"}
    ))
    assert response.status_code == 404
    assert not response.content


@mark.asyncio
async def test_add_context_feature(check_indexes_of_cf, app_client):
    response = await app_client.post('/api/v1/context_features', data=json.dumps(
        {"context_feature": "black"}
    ))
    response.raise_for_status()
    context_features = await app_client.get('/api/v1/context_features')
    assert context_features.json() == {
        'context_features': ["user", "trust", "theme", "black"]
    }


@mark.asyncio
async def test_add_context_feature_exists(app_client):
    response = await app_client.post('/api/v1/context_features', data=json.dumps(
        {"context_feature": "theme"}
    ))
    assert response.status_code == 409
    assert response.content == b"context feature already exists"
