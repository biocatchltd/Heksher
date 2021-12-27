import subprocess
import sys
from os import environ

from yellowbox import docker_client
from yellowbox.extras.postgresql import PostgreSQLService

service: PostgreSQLService
with docker_client() as DC, PostgreSQLService.run(DC) as sql_service:
    environ['HEKSHER_DB_CONNECTION_STRING'] = sql_service.local_connection_string()
    environ['HEKSHER_STARTUP_CONTEXT_FEATURES'] = 'user;trust;theme'

    head_suffix = input('enter head suffix:\n')
    message = input('enter revision message:\n')

    subprocess.run([sys.executable, "-m", "alembic", "upgrade", f"head{head_suffix}"])
    subprocess.run([sys.executable, "-m", "alembic", "revision", "--autogenerate", "-m", f'"{message}"'])
