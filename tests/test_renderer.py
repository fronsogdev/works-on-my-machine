"""Renderer unit tests: valid PNG output and deterministic helper logic."""

from __future__ import annotations

import io
import random
import re
from datetime import UTC, datetime

from PIL import Image

from worker.renderer import (
    HEIGHT,
    NOTARIES,
    WIDTH,
    choose_notary,
    generate_serial_number,
    render_certificate_png,
)

SERIAL_PATTERN = re.compile(r"^WOMM-\d{4}-[A-Z]{2,4}-[0-9A-F]{4}$")


def test_generate_serial_number_format() -> None:
    serial = generate_serial_number(2026)
    assert SERIAL_PATTERN.match(serial), serial
    assert serial.startswith("WOMM-2026-")


def test_generate_serial_number_is_deterministic_with_seeded_rng() -> None:
    first = generate_serial_number(2026, random.Random(42))
    second = generate_serial_number(2026, random.Random(42))
    assert first == second


def test_choose_notary_returns_known_name() -> None:
    assert choose_notary(random.Random(1)) in NOTARIES


def test_render_produces_valid_png() -> None:
    png = render_certificate_png(
        name="Ada Lovelace",
        project="analytical-engine",
        excuse="It worked on my machine.",
        serial_number="WOMM-2026-LGTM-0F3A",
        notary="Baroness Ada von Segfault",
        issued_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
    )
    assert png.startswith(b"\x89PNG\r\n\x1a\n")
    image = Image.open(io.BytesIO(png))
    assert image.format == "PNG"
    assert image.size == (WIDTH, HEIGHT)
    assert image.mode == "RGB"


def test_render_handles_long_excuse() -> None:
    png = render_certificate_png(
        name="Someone",
        project="a-really-long-project-name-that-keeps-going",
        excuse="x " * 200,
        serial_number="WOMM-2026-RTFM-FFFF",
        notary="Sir Renders-a-Lot",
        issued_at=datetime(2026, 5, 5, tzinfo=UTC),
    )
    assert Image.open(io.BytesIO(png)).size == (WIDTH, HEIGHT)
