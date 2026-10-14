"""RQ queue unit tests using fakeredis (no network)."""

from __future__ import annotations

import fakeredis
from rq import Queue, SimpleWorker
from rq.job import Job, JobStatus

from app.config import Settings
from app.task_queue import RENDER_JOB_FUNCTION, create_queue, enqueue_render, queue_depth


def test_enqueue_render_creates_expected_job() -> None:
    settings = Settings()
    connection = fakeredis.FakeRedis()
    queue = create_queue(settings, connection)

    job = enqueue_render(queue, "certificate-1", job_timeout=30)

    assert job.func_name == RENDER_JOB_FUNCTION
    assert job.args == ("certificate-1",)
    assert queue_depth(connection, settings.queue_name) == 1


def test_enqueue_and_dequeue_flow() -> None:
    connection = fakeredis.FakeRedis()
    queue = Queue("certificates", connection=connection)
    job = queue.enqueue("os.getcwd", job_timeout=30)

    worker = SimpleWorker([queue], connection=connection)
    worker.work(burst=True)

    finished = Job.fetch(job.id, connection=connection)
    assert finished.get_status() == JobStatus.FINISHED
    assert finished.return_value()
    assert queue_depth(connection, "certificates") == 0
