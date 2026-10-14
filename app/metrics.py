"""Prometheus metrics and the Redis-backed render-duration window.

Design note (honesty): the render histogram is produced in the *worker*
process, but ``/metrics`` is only served by the API. Instead of inventing a
pushgateway, the worker appends each render duration (in milliseconds) to a
capped Redis list and the API reads that list at scrape time. The histogram
therefore describes the most recent ``render_duration_window`` renders (a
bounded sliding window), not the process lifetime. This limitation is stated
here and on the metric help text.

The counters ``certificates_issued_total`` and ``machines_certified_total``
derive from a single source of truth: the number of certificates with status
``done`` in the database. The queue-depth gauge is the RQ queue length.
"""

from __future__ import annotations

from redis import Redis

RENDER_DURATIONS_KEY = "womm:render_durations_ms"

# Buckets in seconds. Renders are fast; the small buckets are the interesting
# ones. The tail is kept for pathological cases.
RENDER_DURATION_BUCKETS = (0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)


def record_render_duration(connection: Redis, duration_ms: int, window: int) -> None:
    """Prepend a render duration and cap the list to ``window`` entries."""
    pipe = connection.pipeline()
    pipe.lpush(RENDER_DURATIONS_KEY, duration_ms)
    pipe.ltrim(RENDER_DURATIONS_KEY, 0, window - 1)
    pipe.execute()


def read_render_durations(connection: Redis) -> list[int]:
    """Return the recorded render durations in milliseconds, oldest first."""
    raw = connection.lrange(RENDER_DURATIONS_KEY, 0, -1)
    return [int(value) for value in reversed(raw)]


def render_metrics_text(
    *,
    issued_total: int,
    queue_depth: int,
    durations_ms: list[int],
) -> bytes:
    """Render the Prometheus text exposition for a single scrape.

    A fresh ``CollectorRegistry`` is built per scrape so every value reflects
    the state read moments earlier, including the honest sliding-window
    histogram.
    """
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

    registry = CollectorRegistry()

    issued = Counter(
        "certificates_issued_total",
        "Certificates marked done in the database.",
        registry=registry,
    )
    machines = Gauge(
        "machines_certified_total",
        "Machines officially certified as working (same source of truth as "
        "certificates_issued_total).",
        registry=registry,
    )
    depth = Gauge(
        "womm_queue_depth",
        "Number of jobs waiting in the RQ queue.",
        registry=registry,
    )
    duration = Histogram(
        "womm_render_duration_seconds",
        "Render duration observed in the worker; reflects the most recent "
        f"{len(durations_ms)} renders stored in Redis, not the process lifetime.",
        buckets=RENDER_DURATION_BUCKETS,
        registry=registry,
    )

    issued.inc(issued_total)
    machines.set(issued_total)
    depth.set(queue_depth)
    for milliseconds in durations_ms:
        duration.observe(milliseconds / 1000.0)

    return generate_latest(registry)
