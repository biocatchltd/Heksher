#!/bin/sh
set -e
coverage run --branch --context=ut --include="heksher/*" --concurrency=greenlet -m pytest tests/unittests
coverage run -a --branch --context=blackbox --include="heksher/*" --concurrency=greenlet -m pytest tests/blackbox/app
coverage html
coverage report -m
coverage xml