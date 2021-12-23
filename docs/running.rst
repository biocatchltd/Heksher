Running Heksher
=================

Heksher is an HTTP service, running it is best done through the
`docker image <https://hub.docker.com/repository/docker/biocatchltd/heksher>`_.

.. code-block:: console

    docker run -d -p 80:80 --name heksher biocatchltd/heksher -E ...

Dependencies
-----------------
Heksher requires a postgresql database to store its data. The database's connection string should be passed as an
environment variable ``HEKSHER_DB_CONNECTION_STRING`` as a driverless sqlalchemy-style connection string.

.. code-block:: console

    docker run -d -p 80:80 --name heksher biocatchltd/heksher -E HEKSHER_DB_CONNECTION_STRING=postgresql://user:password@host:port/dbname -E ...

The database must be initialized to Heksher's schema. the database's schema is handled with
`alembic <https://alembic.sqlalchemy.org/en/latest/>`_. For convenience, the database can be initialized with
alembic using the Heksher image.

.. code-block:: console

    docker run biocatchltd/heksher alembic upgrade head -E HEKSHER_DB_CONNECTION_STRING=postgresql://user:password@host:port/dbname

.. note::

    Heksher is stateless in respect to its database, meaning that it makes no assumptions during runtime about the
    contents of the database. The database can be swapped out and in at any time between API calls.

Additional Environment Variables
-------------------------------------------

* **HEKSHER_DB_CONNECTION_STRING**: The database connection string (see `above <Dependencies>`_).
* **HEKSHER_STARTUP_CONTEXT_FEATURES**: A semicolon-delimited list of :ref:`concepts:context features`, in order.
  Heksher will adapt the database's existing context features to this list (or raise an error if it cannot). For
  example: ``user;trust;theme``

The following environment variables are optional for logging:

* **HEKSHER_LOGSTASH_HOST**: the logstash host to send logs to.
* **HEKSHER_LOGSTASH_PORT**: the logstash port to send logs to.
* **HEKSHER_LOGSTASH_LEVEL**: the log level to send logs on.
* **HEKSHER_LOGSTASH_TAGS**: additional tags to send with logs.