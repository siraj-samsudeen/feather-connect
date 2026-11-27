"""Row ids (design point 6): UUIDv7, made in Python, so a row's id is known before it is written.

Tests can hand the store ids of their own.
"""

import uuid
from collections.abc import Callable

type NewId = Callable[[], uuid.UUID]


def new_id() -> uuid.UUID:
    """A new UUIDv7, ordered by the time it was made."""
    return uuid.uuid7()
