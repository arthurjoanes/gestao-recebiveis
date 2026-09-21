#!/bin/sh
set -eu
ruff check src tests
ruff format --check src tests
mypy src
alembic upgrade head
pytest
