"""Metrics aggregation unit tests (Redis-backed sliding window)."""

from __future__ import annotations

import fakeredis
from app.metrics import (
    RENDER_DURATIONS_KEY,
    read_render_durations,
    record_render_duration,
    render_metrics_text,
)


def test_record_render_duration_caps_the_window() -> None:
    connection = fakeredis.FakeRedis()
    for duration in range(1, 6):
        record_render_duration(connection, duration, window=3)

    assert read_render_durations(connection) == [3, 4, 5]
    assert connection.llen(RENDER_DURATIONS_KEY) == 3


def test_read_render_durations_is_oldest_first() -> None:
    connection = fakeredis.FakeRedis()
    record_render_duration(connection, 10, window=10)
    record_render_duration(connection, 20, window=10)

    assert read_render_durations(connection) == [10, 20]


def test_render_metrics_text_exposes_expected_series() -> None:
    text = render_metrics_text(issued_total=5, queue_depth=3, durations_ms=[100, 250]).decode()

    assert "certificates_issued_total 5.0" in text
    assert "machines_certified_total 5.0" in text
    assert "womm_queue_depth 3.0" in text
    assert "womm_render_duration_seconds_count 2.0" in text
    assert "womm_render_duration_seconds_sum 0.35" in text
    # Help text states the honest window rather than implying a lifetime sum.
    assert "not the process lifetime" in text
