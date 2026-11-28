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

# The stored data (stored-versions, design § Tables). Record state, record blocks and snapshot
# blocks are written in bulk, set-based and not audited per row (ADR 0022).
PARTITION = Table("fcon.partition", key=("tenant_id", "id"), changes=True)
VERSION = Table("fcon.version", key=("tenant_id", "id"), changes=True)
RECORD_BLOCK = Table("fcon.record_block", key=("tenant_id", "id", "created_at"), changes=False)
RECORD_STATE = Table("fcon.record_state", key=("tenant_id", "id"), changes=True)
DATASET_PROGRESS = Table("fcon.dataset_progress", key=("tenant_id", "dataset_id"), changes=True)
SNAPSHOT_BASE = Table("fcon.snapshot_base", key=("tenant_id", "id"), changes=True)
SNAPSHOT_BLOCK = Table("fcon.snapshot_block", key=("tenant_id", "id"), changes=False)
SNAPSHOT_PIN = Table("fcon.snapshot_pin", key=("tenant_id", "id"), changes=False)
STORED_DATA = (
    PARTITION,
    VERSION,
    RECORD_BLOCK,
    RECORD_STATE,
    DATASET_PROGRESS,
    SNAPSHOT_BASE,
    SNAPSHOT_BLOCK,
    SNAPSHOT_PIN,
)

TABLES = (TENANT, USER, SESSION, SIGN_IN_ATTEMPT, *STORED_DATA)
