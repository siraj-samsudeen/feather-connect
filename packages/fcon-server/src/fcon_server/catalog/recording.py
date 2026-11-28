"""Recording what one package version declares (design decisions 1 to 4 and 7).

All of it in one transaction, serialised per tenant and package by an advisory lock, so two
packages record in parallel and a package version is either all in the catalog or not at all:

1. The package version goes in once (`insert_if_absent`). Recorded already with the same
   checksum, nothing is written; with another, the recording is refused.
2. Each definition finds its entry, the stable identity that versions and settings point to: by
   its name; else, for a rename, by the old name, which the entry then takes; else a new entry.
   A kind never changes.
3. Each definition is copied for this package version, and every entry of the package moves to
   it, or is marked no longer in the code. The operator's values of such entries stay, flagged:
   logged as a warning, and given back to say.

For `fcon catalog record` now, and the install path later.
"""

import logging
from collections import Counter
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from psycopg.types.json import Jsonb

from fcon_server.catalog.definitions import Definition, PackageDefinitions
from fcon_server.catalog.known_settings import Kind
from fcon_server.store.tables import CATALOG_DEFINITION, CATALOG_ENTRY, PACKAGE_VERSION
from fcon_server.store.transaction import Store, Transaction
from fcon_server.users.rights import Action, Caller, require

logger = logging.getLogger("fcon.catalog")


@dataclass(frozen=True)
class Renamed:
    """An entry this recording moved from its old name to its new one."""

    old: str
    new: str


@dataclass(frozen=True)
class FlaggedValue:
    """An operator's value for an entry the code no longer declares: its name and the setting."""

    name: str
    setting: str


@dataclass(frozen=True)
class Recorded:
    """What a recording did: how many of each kind, the renames, the values now flagged.

    `already` is true when the package version was recorded already, with the same definitions,
    and nothing was written.
    """

    package: str
    version: str
    already: bool
    counts: dict[Kind, int]
    renamed: tuple[Renamed, ...] = ()
    flagged: tuple[FlaggedValue, ...] = ()


class ChangedDefinitionsError(Exception):
    """The package version is recorded already, with other definitions: a recorded version never changes."""

    def __init__(self, package: str, version: str) -> None:
        super().__init__(f"{package} {version} is recorded already, with other definitions")
        self.package = package
        self.version = version


class KindChangedError(Exception):
    """The package version declares a known name as another kind."""

    def __init__(self, name: str, was: Kind, now: Kind) -> None:
        super().__init__(f"{name} is a {was}, and cannot become a {now}")
        self.name = name


class RenameAcrossKindsError(Exception):
    """The package version renames an entry of one kind to a name of another."""

    def __init__(self, new: str, new_kind: Kind, old: str, old_kind: Kind) -> None:
        super().__init__(f"{new}, a {new_kind}, cannot be renamed from {old}, a {old_kind}")
        self.new = new
        self.old = old


def _plural(count: int, kind: Kind) -> str:
    """The count and the kind in words: "1 flow", "2 datasets", "0 routes"."""
    return f"{count} {kind}{'' if count == 1 else 's'}"


def counted(recorded: Recorded) -> str:
    """How many of each kind a recording holds: "1 flow, 2 datasets, 0 routes"."""
    return ", ".join(_plural(recorded.counts.get(kind, 0), kind) for kind in Kind)


@dataclass
class _Entry:
    """An entry of the package, locked for the recording."""

    id: UUID
    kind: str
    name: str
    is_in_code: bool
    row_version: int


@dataclass(frozen=True)
class _Checksum:
    """A recorded package version's checksum."""

    checksum: str


@dataclass(frozen=True)
class _Flagged:
    """An operator's value of an entry no longer in the code, as the query reads it."""

    name: str
    setting: str


_LOCK = "SELECT pg_advisory_xact_lock(hashtextextended(%(tenant_id)s || '/' || %(package)s, 0))"

_CHECKSUM = """
    SELECT checksum FROM fcon.package_version
    WHERE tenant_id = %(tenant_id)s AND package = %(package)s AND version = %(version)s
"""

# Every entry of the package, locked in id order (convention 13).
_ENTRIES = """
    SELECT id, kind, name, is_in_code, row_version FROM fcon.catalog_entry
    WHERE tenant_id = %(tenant_id)s AND package = %(package)s
    ORDER BY id
    FOR UPDATE
"""

_FLAGGED = """
    SELECT e.name, s.setting
    FROM fcon.operator_setting s
    JOIN fcon.catalog_entry e ON e.tenant_id = s.tenant_id AND e.id = s.entry_id
    WHERE s.tenant_id = %(tenant_id)s AND e.tenant_id = %(tenant_id)s
        AND e.package = %(package)s AND NOT e.is_in_code AND s.value IS NOT NULL
    ORDER BY e.name, s.setting
"""


class _Recording:
    """One package version's recording inside its transaction: the entries, as they change.

    `_by_name` starts as every entry of the package, locked; an entry a rename continues leaves it
    under its old name. `_declared` gathers the entries already there that this version
    declares. An entry made by this version is in neither, so `retire_the_rest` (every entry left
    in `_by_name` and not declared) never touches it.
    """

    def __init__(self, tx: Transaction, definitions: PackageDefinitions, version_id: UUID) -> None:
        self._tx = tx
        self._definitions = definitions
        self._version_id = version_id
        found = tx.fetch_all(_Entry, _ENTRIES, {"package": definitions.package})
        self._by_name = {entry.name: entry for entry in found}
        self._declared: set[UUID] = set()
        self.renamed: list[Renamed] = []

    def _continued_entry(self, definition: Definition) -> _Entry | None:
        """The entry this definition continues: by its name, else by the old name of a rename.

        A rename is noted in `renamed`, and its entry leaves `_by_name` under the old name.
        """
        entry = self._by_name.get(definition.name)
        if entry is not None:
            if entry.kind != definition.kind:
                raise KindChangedError(definition.name, Kind(entry.kind), definition.kind)
            return entry
        old = self._by_name.get(definition.renamed_from or "")
        if old is None:
            return None
        if old.kind != definition.kind:
            raise RenameAcrossKindsError(definition.name, definition.kind, old.name, Kind(old.kind))
        self.renamed.append(Renamed(old.name, definition.name))
        del self._by_name[old.name]
        return old

    def _move_or_make_entry(self, definition: Definition) -> UUID:
        """Moves the definition's entry to this version under its name, or makes it; gives its id."""
        entry = self._continued_entry(definition)
        if entry is None:
            values = {"kind": definition.kind.value, "name": definition.name, "package": self._definitions.package}
            key = self._tx.insert(CATALOG_ENTRY, values | {"package_version_id": self._version_id, "is_in_code": True})
            return cast(UUID, key["id"])
        values = {"name": definition.name, "package_version_id": self._version_id, "is_in_code": True}
        self._tx.update(CATALOG_ENTRY, {"id": entry.id}, values, entry.row_version)
        self._declared.add(entry.id)
        return entry.id

    def declare(self, definition: Definition) -> None:
        """Records one definition: its entry, then this version's copy of it."""
        copy = {
            "package_version_id": self._version_id,
            "entry_id": self._move_or_make_entry(definition),
            "name": definition.name,
            "renamed_from": definition.renamed_from,
            "definition": Jsonb(definition.body),
        }
        self._tx.insert(CATALOG_DEFINITION, copy)

    def retire_the_rest(self) -> None:
        """Marks every entry of the package this version does not declare as no longer in the code."""
        for entry in self._by_name.values():
            if entry.id not in self._declared and entry.is_in_code:
                self._tx.update(CATALOG_ENTRY, {"id": entry.id}, {"is_in_code": False}, entry.row_version)

    def flagged(self) -> tuple[FlaggedValue, ...]:
        """The operator's values of the package's entries no longer in the code."""
        found = self._tx.fetch_all(_Flagged, _FLAGGED, {"package": self._definitions.package})
        return tuple(FlaggedValue(row.name, row.setting) for row in found)


def _record(tx: Transaction, definitions: PackageDefinitions) -> Recorded:
    """Records the package version in `tx`, holding the package's lock."""
    package, version = definitions.package, definitions.version
    counts = Counter(each.kind for each in definitions.definitions)
    tx.execute(_LOCK, {"package": package})
    values = {"package": package, "version": version, "checksum": definitions.checksum}
    key = tx.insert_if_absent(PACKAGE_VERSION, values)
    if key is None:
        recorded = tx.fetch_one(_Checksum, _CHECKSUM, {"package": package, "version": version})
        if recorded is None or recorded.checksum != definitions.checksum:
            raise ChangedDefinitionsError(package, version)
        return Recorded(package, version, already=True, counts=dict(counts))
    recording = _Recording(tx, definitions, cast(UUID, key["id"]))
    for definition in definitions.definitions:
        recording.declare(definition)
    recording.retire_the_rest()
    flagged = recording.flagged()
    return Recorded(package, version, False, dict(counts), tuple(recording.renamed), flagged)


def record(store: Store, caller: Caller, definitions: PackageDefinitions) -> Recorded:
    """Records one package version's definitions, for a caller who may record the catalog.

    Logs one line per recording and a warning per flagged operator value. Raises
    `ChangedDefinitionsError`, `KindChangedError` or `RenameAcrossKindsError`, and then writes
    nothing.
    """
    require(store, caller, Action.RECORD_CATALOG)
    with store.transaction(caller.context) as tx:
        recorded = _record(tx, definitions)
    if recorded.already:
        logger.info("%s %s is recorded already", recorded.package, recorded.version)
        return recorded
    logger.info("recorded %s %s: %s", recorded.package, recorded.version, counted(recorded))
    for value in recorded.flagged:
        logger.warning("the operator's %s of %s is for a name the code no longer has", value.setting, value.name)
    return recorded
