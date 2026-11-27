"""The context of a request or job: who is calling, for which tenant, under which request id.

Design point 1 and decision 5. Passed by hand; no code reads the tenant from anywhere else:
the context variable `bind` sets is read by the log formatter alone (decision 5).
"""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    """Who is calling, for which tenant, under which request id, and why.

    `actor` is `user:<id>`, `token:<id>` or `system:<name>`; `reason`, when a feature gives one,
    goes on the audit records it writes.
    """

    tenant_id: str
    actor: str
    request_id: str
    reason: str | None = None


_current: ContextVar[Context | None] = ContextVar("fcon_context", default=None)


@contextmanager
def bind(context: Context) -> Generator[Context]:
    """Makes `context` the current request's or job's, for the log, until the block ends.

    Used at the edge that starts a request or job: the log writes this context's tenant and
    request id on every line. Only the log reads it; code takes the context by hand.
    """
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def bound() -> Context | None:
    """The context of the current request or job, for the log formatter only."""
    return _current.get()
