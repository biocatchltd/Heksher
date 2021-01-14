FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

RUN apt-get update && \
    apt-get -y install gcc build-essential

RUN mkdir -p /usr/src/app/heksher

WORKDIR /usr/src/app/heksher

RUN pip install poetry

RUN poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-dev --no-root -E alembic
# needed for poetry version to work
RUN pip install requests

COPY . /usr/src/app/heksher

RUN export APP_VERSION=$(poetry version | cut -d' ' -f2) && echo "__version__ = '$APP_VERSION'" > heksher/_version.py

ENV PYTHONPATH=${PYTHONPATH}:/usr/src/app/heksher
ENV PYTHONOPTIMIZE=1
ENV WEB_CONCURRENCY=1
ENV MODULE_NAME=heksher.main
