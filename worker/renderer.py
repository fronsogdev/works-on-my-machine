"""Pillow renderer for the certificate image.

The layout is intentionally simple and font-file-free: Pillow's bundled default
font is loaded at several sizes via ``ImageFont.load_default(size=...)``.
"""

from __future__ import annotations

import io
import random
import textwrap
from datetime import datetime

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1200
HEIGHT = 900

PAPER = (250, 247, 240)
INK = (32, 32, 38)
ACCENT = (150, 32, 32)
MUTED = (110, 104, 96)

NOTARIES: tuple[str, ...] = (
    "Baroness Ada von Segfault",
    "Notary Public of the Ministry of Works On My Machine",
    "Dr. Cache Invalidation, Esq.",
    "The Right Honourable Merge Conflict",
    "Keeper of the Sacred Localhost",
    "Madame Nullpointer Exception",
    "Sir Renders-a-Lot",
    "The Off-By-One Ombudsman",
    "Archduke Stack Trace III",
)

SERIAL_WORDS: tuple[str, ...] = ("LGTM", "WAI", "FYI", "TBD", "RTFM")

# ``load_default(size=...)`` returns a FreeType font, but the bitmap default is
# returned when no size is given; the union keeps the type honest.
Font = ImageFont.FreeTypeFont | ImageFont.ImageFont


def generate_serial_number(year: int, rng: random.Random | None = None) -> str:
    """Return a joking-but-plausible serial number."""
    source = rng or random
    word = source.choice(SERIAL_WORDS)
    token = "".join(source.choice("0123456789ABCDEF") for _ in range(4))
    return f"WOMM-{year}-{word}-{token}"


def choose_notary(rng: random.Random | None = None) -> str:
    """Return a random fake notary name."""
    source = rng or random
    return source.choice(NOTARIES)


def _font(size: int) -> Font:
    return ImageFont.load_default(size=size)


def _centered_text(
    draw: ImageDraw.ImageDraw,
    y: int,
    text: str,
    font: Font,
    fill: tuple[int, int, int],
) -> None:
    left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
    draw.text(((WIDTH - (right - left)) / 2 - left, y), text, font=font, fill=fill)


def _draw_stamp(image: Image.Image, label: str) -> None:
    """Paste a rotated red 'CERTIFIED' stamp onto the image."""
    stamp = Image.new("RGBA", (360, 360), (0, 0, 0, 0))
    stamp_draw = ImageDraw.Draw(stamp)
    stamp_draw.ellipse((10, 10, 350, 350), outline=ACCENT, width=6)
    stamp_draw.ellipse((24, 24, 336, 336), outline=ACCENT, width=2)
    stamp_font = _font(30)
    lines = ["WORKS ON", "MY MACHINE", "CERTIFIED"]
    start_y = 130
    for offset, line in enumerate(lines):
        left, top, right, _ = stamp_draw.textbbox((0, 0), line, font=stamp_font)
        stamp_draw.text(
            ((360 - (right - left)) / 2 - left, start_y + offset * 40),
            line,
            font=stamp_font,
            fill=ACCENT,
        )
    rotated = stamp.rotate(15, resample=Image.Resampling.BICUBIC, expand=True)
    image.paste(rotated, (WIDTH - rotated.width - 60, HEIGHT - rotated.height - 30), rotated)


def render_certificate_png(
    *,
    name: str,
    project: str,
    excuse: str,
    serial_number: str,
    notary: str,
    issued_at: datetime,
) -> bytes:
    """Render a certificate as PNG bytes."""
    image = Image.new("RGB", (WIDTH, HEIGHT), PAPER)
    draw = ImageDraw.Draw(image)

    draw.rectangle((24, 24, WIDTH - 24, HEIGHT - 24), outline=ACCENT, width=4)
    draw.rectangle((36, 36, WIDTH - 36, HEIGHT - 36), outline=INK, width=1)

    _centered_text(draw, 70, "Certificate of Works On My Machine", _font(46), INK)
    _centered_text(
        draw, 130, "This is to certify that, contrary to all evidence,", _font(22), MUTED
    )
    _centered_text(draw, 168, "the following really does work on a machine:", _font(22), MUTED)

    _centered_text(draw, 235, name, _font(54), ACCENT)
    _centered_text(draw, 320, f"project: {project}", _font(30), INK)

    wrapped = textwrap.wrap(f'Excuse on record: "{excuse}"', width=52) or [""]
    for offset, line in enumerate(wrapped[:3]):
        _centered_text(draw, 400 + offset * 40, line, _font(24), INK)

    draw.line((120, 560, WIDTH - 120, 560), fill=MUTED, width=2)

    _centered_text(draw, 600, f"Serial number: {serial_number}", _font(26), INK)
    _centered_text(draw, 648, f"Notarized by: {notary}", _font(24), MUTED)
    _centered_text(
        draw, 694, f"Stamped: {issued_at.strftime('%Y-%m-%d %H:%M UTC')}", _font(22), MUTED
    )

    _draw_stamp(image, serial_number)

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
