import sys
from subprocess import run

from pytest import fixture
from yellowbox import docker_client as _docker_client
from yellowbox.extras.postgresql import PostgreSQLService


@fixture(scope='session')
def docker_client():
    with _docker_client() as dc:
        yield dc


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
