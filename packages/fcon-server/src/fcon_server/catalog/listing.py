"""The catalog as a list: every flow, dataset and route the code declares now (design decision 2).

"Now" is the latest recorded version of each package; an entry it no longer declares is left out.
For `fcon catalog list` now, and the dashboard later.
"""

from dataclasses import dataclass

from fcon_server.catalog.known_settings import Kind
from fcon_server.store.transaction import Store
from fcon_server.users.rights import Action, Caller, require


@dataclass(frozen=True)
class ListedEntry:
    """One flow, dataset or route as the list shows it, with the package version it is from."""

    name: str
    kind: Kind
    package: str
    version: str


@dataclass(frozen=True)
class _Listed:
    """One entry as the list's query reads it, the kind as text."""

    name: str
    kind: str
    package: str
    version: str


_LIST = """
    SELECT e.name, e.kind, e.package, v.version
    FROM fcon.catalog_entry e
    JOIN fcon.package_version v ON v.tenant_id = e.tenant_id AND v.id = e.package_version_id
    WHERE e.tenant_id = %(tenant_id)s AND v.tenant_id = %(tenant_id)s AND e.is_in_code
    ORDER BY e.name COLLATE "und-x-icu"
"""


def list_catalog(store: Store, caller: Caller) -> list[ListedEntry]:
    """Every entry the code declares now, sorted by name; for anyone who may see settings."""
    require(store, caller, Action.SEE_SETTINGS)
    with store.transaction(caller.context) as tx:
        found = tx.fetch_all(_Listed, _LIST)
    return [ListedEntry(row.name, Kind(row.kind), row.package, row.version) for row in found]
