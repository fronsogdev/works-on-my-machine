"""Developer excuses, served with a straight face whenever the server errors."""

from __future__ import annotations

import random

EXCUSES: tuple[str, ...] = (
    "It worked on my machine.",
    "That is a caching issue. Definitely caching.",
    "The intern touched the config again.",
    "Works in Docker. Are you running Docker?",
    "The database is just having a moment.",
    "Must be a DNS problem. It is always DNS.",
    "I only changed a comment, I promise.",
    "The tests passed before the meeting.",
    "Cosmic rays flipped a bit. Not my code.",
    "It is an undocumented feature.",
    "The cloud is a bit cloudy today.",
    "Git blame says it was you.",
    "Have you tried turning it off and on again?",
    "That code path is only covered on Tuesdays.",
    "We are between two deployments right now.",
)


def random_excuse() -> str:
    """Return a random excuse from the list."""
    return random.choice(EXCUSES)
