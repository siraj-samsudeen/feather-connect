"""The context of a request or job (design point 1 and decision 5): who is
calling, for which tenant, under which request id. Passed by hand; no code
reads the tenant from anywhere else."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Context:
    """`actor` is `user:<id>`, `token:<id>` or `system:<name>`; `reason`, when
    a feature gives one, goes on the audit records it writes."""

    tenant_id: str
    actor: str
    request_id: str
    reason: str | None = None
