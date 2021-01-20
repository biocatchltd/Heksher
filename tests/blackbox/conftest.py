import sys
from subprocess import run

from docker import DockerClient
from pytest import fixture
from starlette.testclient import TestClient
from yellowbox.extras.postgresql import PostgreSQLService

from heksher.main import app

# apparently this works
from tests.blackbox.test_v1api_settings import size_limit_setting  # noqa: F401


@fixture(scope='session')
def docker_client():
    return DockerClient.from_env()


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
    #create_all(sql_service.local_connection_string())
    run([sys.executable, 'alembic/from_scratch.py', sql_service.local_connection_string()])
    yield


@fixture
def app_client(monkeypatch, sql_service, purge_sql):
    monkeypatch.setenv('HEKSHER_DB_CONNECTION_STRING', sql_service.local_connection_string())
    monkeypatch.setenv('HEKSHER_STARTUP_CONTEXT_FEATURES', 'user;trust;theme')

    with TestClient(app) as app_client:
        yield app_client
