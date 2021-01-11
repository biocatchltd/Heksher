from os import getenv

from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine

from heksher.db_logic.metadata import metadata


def create_all(connection_string):
    engine = create_engine(connection_string)
    # then, load the Alembic configuration and generate the
    # version table, "stamping" it with the most recent rev:
    alembic_cfg = Config("alembic.ini")
    command.stamp(alembic_cfg, "head")

    metadata.create_all(engine)


if __name__ == '__main__':
    conn_string = getenv('HEKSHER_DB_CONNECTION_STRING')
    if not conn_string:
        raise RuntimeError('must set env var HEKSHER_DB_CONNECTION_STRING')
    create_all(conn_string)
