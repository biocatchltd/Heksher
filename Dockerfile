FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

RUN apt-get update && \
    apt-get -y install gcc build-essential

RUN mkdir -p /usr/src/app/heksher

WORKDIR /usr/src/app/heksher

RUN curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py | POETRY_HOME=/opt/poetry python && \
    cd /usr/local/bin && \
    ln -s /opt/poetry/bin/poetry && \
    poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock* ./
RUN poetry install --no-dev --no-root -E alembic

COPY . /usr/src/app/heksher
COPY ./app /app

RUN export APP_VERSION=$(poetry version | cut -d' ' -f2) && echo "__version__ = '$APP_VERSION'" > heksher/_version.py

ENV PYTHONPATH=${PYTHONPATH}:/usr/src/app/heksher
ENV PYTHONOPTIMIZE=1
ENV WEB_CONCURRENCY=1
ENV MODULE_NAME=heksher.main
