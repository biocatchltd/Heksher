FROM python:3.11.6-slim-bookworm

RUN apt-get update && \
    apt-get -y install gcc build-essential

RUN mkdir -p /usr/src/app/heksher

WORKDIR /usr/src/app/heksher

RUN pip install pip --upgrade
RUN pip install poetry
RUN poetry config virtualenvs.create false
COPY pyproject.toml poetry.lock ./
RUN poetry run pip install --upgrade pip
RUN poetry install --no-dev --no-root
# poetry removes its own dependencies, so we need to install them again
RUN pip install requests

COPY . /usr/src/app/heksher

RUN export APP_VERSION=$(poetry version | cut -d' ' -f2) && echo "__version__ = '$APP_VERSION'" > heksher/_version.py

ENV PYTHONPATH=${PYTHONPATH}:/usr/src/app/heksher
ENV PYTHONOPTIMIZE=1

CMD ["uvicorn", "heksher.main:app", "--host", "0.0.0.0", "--port", "80", "--factory"]
