from pytest import raises
from starlette.testclient import TestClient

from heksher.main import app


def test_startup_existing_contexts(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["user", "trust", "theme"]')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 1), ('theme', 2);
        """)

    with TestClient(app):
        pass


def test_startup_existing_unexpected_contexts(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["user", "trust", "theme"]')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 1), ('theme', 2), ('color', 3);
        """)

    with raises(RuntimeError):
        with TestClient(app):
            pass

def test_startup_existing_bad_order(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["user", "trust", "theme"]')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 2), ('theme', 1);
        """)

    with raises(RuntimeError):
        with TestClient(app):
            pass


def test_startup_existing_contexts_with_bad_indices(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["user", "trust", "theme"]')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('user', 0), ('trust', 3), ('theme', 5);
        """)

    with TestClient(app):
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

def test_startup_existing_contexts_new_contexts(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', '["user", "trust", "theme"]')

    with sql_service.connection() as connection:
        connection.execute("""
        INSERT into context_features VALUES ('trust', 0);
        """)

    with TestClient(app):
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