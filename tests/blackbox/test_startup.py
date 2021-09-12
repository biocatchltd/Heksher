from logging import getLogger
from time import sleep

import aiologstash
from aiologstash import create_tcp_handler
from async_asgi_testclient import TestClient
from pytest import mark, raises
from yellowbox.extras.logstash import FakeLogstashService

from heksher._version import __version__
from heksher.main import app


@mark.asyncio
async def test_startup_existing_contexts(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 1), ('theme', 2);
        """)

    async with TestClient(app):
        pass


@mark.asyncio
async def test_startup_existing_unexpected_contexts(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 1), ('theme', 2), ('color', 3);
        """)

    with raises(Exception):
        ''' async_asgi_testclient raises Exception for any exception on startup, so we can't be more specific  '''
        async with TestClient(app):
            pass


@mark.asyncio
async def test_startup_existing_bad_order(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 2), ('theme', 1);
        """)

    with raises(Exception):
        async with TestClient(app):
            pass


@mark.asyncio
async def test_startup_existing_contexts_with_bad_indices(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 3), ('theme', 5);
        """)

    async with TestClient(app):
        pass

    with sql_service.connection() as connection:
        results = connection.execute("""
        SELECT * FROM context_features;
        """)
    rows = {row['name']: row['index'] for row in results}
    assert rows == {
        'user': 0,
        'trust': 1,
        'theme': 2
    }


@mark.asyncio
async def test_startup_existing_contexts_new_contexts(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('trust', 0);
        """)

    async with TestClient(app):
        pass

    with sql_service.connection() as connection:
        results = connection.execute("""
        SELECT * FROM context_features;
        """)
    rows = {row['name']: row['index'] for row in results}
    assert rows == {
        'user': 0,
        'trust': 1,
        'theme': 2
    }


@mark.asyncio
async def test_startup_logstash(monkeypatch, sql_service, purge_sql):
    with FakeLogstashService().start() as logstash:
        monkeypatch.setenv('HEKSHER_LOGSTASH_HOST', logstash.local_host)
        monkeypatch.setenv('HEKSHER_LOGSTASH_PORT', str(logstash.port))
        monkeypatch.setenv('HEKSHER_LOGSTASH_TAGS', 'a:b c:d')

        monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
        monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

        handler = None

        async def mock_create_handler(*args, **kwargs):
            global handler
            handler = await create_tcp_handler(*args, **kwargs)
            return handler

        monkeypatch.setattr(aiologstash, 'create_tcp_handler', mock_create_handler)

        async with TestClient(app):
            sleep(0.1)  # wait for logstash records
            # new context features were added, we should be seeing their logs now
            assert logstash.records
            for record in logstash.records:
                assert record['heksher_version'] == __version__
                assert record['a'] == 'b'
                assert record['c'] == 'd'

        getLogger().removeHandler(handler)
