"""The product's tables, each described once (design § The store).

Each gives its name in full, its key (starting with `tenant_id`), whether its rows change (then
it has `updated_at`, `updated_by` and `row_version`), and its secret columns, which the audit log
never shows. A test checks each against the database.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Table:
    """One table as the store writes it: its full name, its key, whether its rows change, its secrets."""

    name: str
    key: tuple[str, ...]
    changes: bool
    secret: frozenset[str] = frozenset()


TENANT = Table("fcon.tenant", key=("tenant_id",), changes=True)

USER = Table("fcon.user", key=("tenant_id", "id"), changes=True, secret=frozenset({"password_hash"}))
SESSION = Table("fcon.session", key=("tenant_id", "id"), changes=True, secret=frozenset({"id_hash", "form_token"}))
SIGN_IN_ATTEMPT = Table("fcon.sign_in_attempt", key=("tenant_id", "id"), changes=False)

TABLES = (TENANT, USER, SESSION, SIGN_IN_ATTEMPT)
