#!/bin/sh
# Worker entrypoint: run an RQ worker against the configured queue.
#
# `exec` replaces this shell with the worker, so RQ is PID 1 and receives
# SIGTERM directly. RQ handles the signal with a warm shutdown: the job that is
# in flight finishes before the process exits.
set -eu

echo "Starting RQ worker on queue ${WOMM_QUEUE_NAME:-certificates}"
exec rq worker \
    --url "${WOMM_REDIS_URL:?WOMM_REDIS_URL must be set}" \
    --path /app \
    "${WOMM_QUEUE_NAME:-certificates}"
