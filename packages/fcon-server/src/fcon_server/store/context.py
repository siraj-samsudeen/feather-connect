"""The context of a request or job (design point 1 and decision 5): who is
calling, for which tenant, under which request id. Passed by hand; no code
reads the tenant from anywhere else: the context variable `bind` sets is read
by the log formatter alone (decision 5)."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    """`actor` is `user:<id>`, `token:<id>` or `system:<name>`; `reason`, when
    a feature gives one, goes on the audit records it writes."""

    tenant_id: str
    actor: str
    request_id: str
    reason: str | None = None


_current: ContextVar[Context | None] = ContextVar("fcon_context", default=None)


@contextmanager
def bind(context: Context) -> Generator[Context]:
    """At the edge that starts a request or job: the log writes this
    context's tenant and request id on every line until the block ends.
    Only the log reads it; code takes the context by hand."""
    token = _current.set(context)
    try:
        yield context
    finally:
        _current.reset(token)


def bound() -> Context | None:
    """The context of the current request or job, for the log formatter only."""
    return _current.get()
