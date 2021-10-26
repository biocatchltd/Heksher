#!/bin/sh
set -e
coverage run --branch --include="heksher/*" --concurrency=greenlet -m pytest tests -s -x
coverage html
coverage report -m
coverage xml