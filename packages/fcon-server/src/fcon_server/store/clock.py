"""The one clock that says "now", handed to the code (design point 7).

The system's clock in the product, a fixed one in tests. Always aware, in UTC.
"""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """What the code asks for the current time."""

    def now(self) -> datetime:
        """The current time, aware, in UTC."""
        ...


class SystemClock:
    """The computer's clock: the product's."""

    def now(self) -> datetime:
        """The computer's current time, in UTC."""
        return datetime.now(UTC)


class FixedClock:
    """A clock that says one time until a test moves it."""

    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        """The time the test set."""
        return self.at
