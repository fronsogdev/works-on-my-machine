"""RQ queue access.

The queue is a thin wrapper over a synchronous Redis client. The API is async,
so callers wrap these functions with ``run_in_threadpool`` to keep the event
loop free.
"""

from __future__ import annotations

import redis
from rq import Queue
from rq.job import Job

from app.config import Settings

RENDER_JOB_FUNCTION = "worker.tasks.render_certificate"


def create_redis(settings: Settings) -> redis.Redis:
    """Create the synchronous Redis client used for RQ and metrics."""
    return redis.Redis.from_url(settings.redis_url)


def create_queue(settings: Settings, connection: redis.Redis | None = None) -> Queue:
    """Create the RQ queue, optionally reusing an existing Redis connection."""
    if connection is None:
        connection = create_redis(settings)
    return Queue(settings.queue_name, connection=connection)


def enqueue_render(
    queue: Queue,
    certificate_id: str,
    *,
    job_timeout: int = 120,
) -> Job:
    """Enqueue a render job and return the RQ job."""
    return queue.enqueue(RENDER_JOB_FUNCTION, certificate_id, job_timeout=job_timeout)


def queue_depth(connection: redis.Redis, queue_name: str) -> int:
    """Return the number of jobs waiting in the named RQ queue."""
    return int(connection.llen(f"rq:queue:{queue_name}"))
