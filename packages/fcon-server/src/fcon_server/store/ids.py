"""Ids (design point 6): UUIDv7, made in Python, so a row's id is known before
it is written and tests can hand the store ids of their own."""

import uuid
from collections.abc import Callable

type NewId = Callable[[], uuid.UUID]


def new_id() -> uuid.UUID:
    return uuid.uuid7()
