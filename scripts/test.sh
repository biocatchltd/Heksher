#!/bin/sh
python -m pytest tests -s -x --cov=heksher --cov-report=xml --cov-report=term-missing