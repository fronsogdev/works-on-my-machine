#!/bin/sh
# API entrypoint: bring the schema up to date, then run the server.
#
# `exec` replaces this shell with uvicorn, so uvicorn becomes PID 1 and receives
# SIGTERM/SIGINT directly. That is what lets uvicorn run its lifespan shutdown
# (closing the database engine and the Redis connection) on `docker stop`.
set -eu

echo "Applying database migrations"
alembic -c migrations/alembic.ini upgrade head

echo "Starting API on port ${WOMM_PORT:-8000}"
exec uvicorn app.main:app --host 0.0.0.0 --port "${WOMM_PORT:-8000}"
