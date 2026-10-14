"""Worker entrypoint.

Runs an RQ worker against the configured queue. RQ installs SIGINT/SIGTERM
handlers and performs a warm shutdown: the in-flight job finishes before the
process exits.
"""

from __future__ import annotations

import sys

from app.config import get_settings
from app.logging_setup import configure_logging, get_logger
from app.task_queue import create_redis
from rq import Queue, Worker


def main() -> int:
    """Start the worker and process jobs until stopped."""
    settings = get_settings()
    configure_logging(settings.log_level)
    connection = create_redis(settings)
    queue = Queue(settings.queue_name, connection=connection)
    get_logger().info("worker_starting", queue_name=settings.queue_name)
    worker = Worker([queue], connection=connection)
    worker.work()
    return 0


if __name__ == "__main__":
    sys.exit(main())
