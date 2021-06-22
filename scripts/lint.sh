#!/bin/sh
# run various linters
set -e
echo "running isort..."
python -m isort . -c
echo "running flake8..."
python -m flake8 --max-line-length 120 heksher tests
echo "running mypy..."
python3 -m mypy --show-error-codes heksher
