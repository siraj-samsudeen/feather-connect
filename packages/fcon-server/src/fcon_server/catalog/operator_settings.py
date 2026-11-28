"""The operator's settings of a flow, dataset or route (design decisions 5 to 9).

The value in force is the operator's, else the code's (from the latest recorded package version
that declares the entry), else the product's default. An operator's value is one row per entry
and setting: set to a value of the setting's type, cleared to null, never deleted.

- A value is set only on an entry the code still declares; it can be cleared on any.
- In a protected environment a change needs a reason, the caller's context's reason, which the
  store writes on the change's audit record. Without one the change is refused.
- Every refused change (no reason, a wrong value, a setting the kind lacks or the code decides,
  an unknown name, a name no longer in the code) is audited as `refused`, in a transaction of its
  own, and nothing else is written (R10.4).
- Seeing needs the right to see settings; setting and clearing, the right to change them.

For `fcon settings` now, and the dashboard later.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, LiteralString
from uuid import UUID

from fcon_server.catalog.known_settings import Kind, Setting, SettingRefusedError, check, setting_named, settings_of
from fcon_server.store.tables import OPERATOR_SETTING
from fcon_server.store.transaction import Store, Transaction
from fcon_server.users.rights import Action, Caller, require


class Layer(StrEnum):
    """Where the value in force comes from."""

    OPERATOR = "operator"
    CODE = "code"
    DEFAULT = "default"


@dataclass(frozen=True)
class InForce:
    """One setting's value in force, where it comes from, and, for an operator's, who set it and when."""

    setting: str
    value: str
    layer: Layer
    changed_by: str | None = None
    changed_at: datetime | None = None


@dataclass(frozen=True)
class EntrySettings:
    """An entry, the package version it is from, and every setting of its kind in force, in the list's order.

    For an entry no longer in the code, `version` is the last that declared it.
    """

    name: str
    kind: Kind
    package: str
    version: str
    is_in_code: bool
    settings: tuple[InForce, ...]


@dataclass(frozen=True)
class Changed:
    """What a set did: the value in its canonical spelling; `already` when it was that already and nothing was written."""

    name: str
    setting: str
    value: str
    already: bool


@dataclass(frozen=True)
class Cleared:
    """What a clear did: whether there was an operator's value, and the value in force now."""

    name: str
    setting: str
    had_value: bool
    in_force: InForce


@dataclass(frozen=True)
class OperatorValue:
    """An operator's value, flagged when its entry is no longer in the code."""

    name: str
    setting: str
    value: str
    is_in_code: bool


class NoSuchEntryError(Exception):
    """No flow, dataset or route has the name."""

    def __init__(self, name: str) -> None:
        super().__init__(f"no flow, dataset or route is named {name}")
        self.name = name


class NotInCodeError(Exception):
    """The entry is no longer in the code: its values can be cleared, not set."""

    def __init__(self, name: str) -> None:
        super().__init__(f"{name} is no longer in the code; its values can be cleared, not set")
        self.name = name


class NeedsAReasonError(Exception):
    """A protected environment refused a change that gave no reason."""

    def __init__(self, name: str) -> None:
        super().__init__(f"{name} was not changed: a protected environment needs a reason for every change")
        self.name = name


@dataclass(frozen=True)
class _Entry:
    """An entry as the queries read it, with the code's values of its settings."""

    id: UUID
    kind: str
    name: str
    package: str
    version: str
    is_in_code: bool
    code: dict[str, Any]


@dataclass(frozen=True)
class _Value:
    """An operator's value of one setting, null once cleared, with who changed it last and when."""

    id: UUID
    setting: str
    value: str | None
    updated_by: str
    updated_at: datetime
    row_version: int


@dataclass(frozen=True)
class _Listed:
    """An operator's value as the list's query reads it."""

    name: str
    setting: str
    value: str
    is_in_code: bool


_ENTRY = """
    SELECT e.id, e.kind, e.name, e.package, v.version, e.is_in_code,
        COALESCE(d.definition -> 'settings', '{}'::jsonb) AS code
    FROM fcon.catalog_entry e
    JOIN fcon.package_version v ON v.tenant_id = e.tenant_id AND v.id = e.package_version_id
    JOIN fcon.catalog_definition d
        ON d.tenant_id = e.tenant_id AND d.package_version_id = e.package_version_id AND d.entry_id = e.id
    WHERE e.tenant_id = %(tenant_id)s AND v.tenant_id = %(tenant_id)s AND d.tenant_id = %(tenant_id)s
        AND e.name = %(name)s
"""

# A change holds the entry, so a recording cannot take it out of the code meanwhile.
_ENTRY_HELD = _ENTRY + " FOR SHARE OF e"

_VALUES = """
    SELECT id, setting, value, updated_by, updated_at, row_version FROM fcon.operator_setting
    WHERE tenant_id = %(tenant_id)s AND entry_id = %(entry_id)s AND value IS NOT NULL
"""

# The row to change, locked (convention 13).
_VALUE_HELD = """
    SELECT id, setting, value, updated_by, updated_at, row_version FROM fcon.operator_setting
    WHERE tenant_id = %(tenant_id)s AND entry_id = %(entry_id)s AND setting = %(setting)s
    FOR UPDATE
"""

_LIST = """
    SELECT e.name, s.setting, s.value, e.is_in_code
    FROM fcon.operator_setting s
    JOIN fcon.catalog_entry e ON e.tenant_id = s.tenant_id AND e.id = s.entry_id
    WHERE s.tenant_id = %(tenant_id)s AND e.tenant_id = %(tenant_id)s AND s.value IS NOT NULL
    ORDER BY e.name COLLATE "und-x-icu", s.setting COLLATE "und-x-icu"
"""


def _entry(tx: Transaction, name: str, query: LiteralString = _ENTRY) -> _Entry:
    """The entry named `name`; raises `NoSuchEntryError` when there is none."""
    found = tx.fetch_one(_Entry, query, {"name": name})
    if found is None:
        raise NoSuchEntryError(name)
    return found


def _below_the_operator(entry: _Entry, setting: Setting) -> InForce:
    """The value in force without an operator's: the code's, else the product's default."""
    if setting.name in entry.code:
        return InForce(setting.name, str(entry.code[setting.name]), Layer.CODE)
    return InForce(setting.name, setting.default, Layer.DEFAULT)


def _in_force(entry: _Entry, setting: Setting, value: _Value | None) -> InForce:
    """The value in force of one setting, given the operator's value, if any."""
    if value is None or value.value is None:
        return _below_the_operator(entry, setting)
    return InForce(setting.name, value.value, Layer.OPERATOR, value.updated_by, value.updated_at)


def effective_settings(store: Store, caller: Caller, name: str) -> EntrySettings:
    """The entry named `name` and every setting of its kind in force; for anyone who may see settings.

    Raises `NoSuchEntryError` when no entry has the name.
    """
    require(store, caller, Action.SEE_SETTINGS)
    with store.transaction(caller.context) as tx:
        entry = _entry(tx, name)
        values = {value.setting: value for value in tx.fetch_all(_Value, _VALUES, {"entry_id": entry.id})}
    kind = Kind(entry.kind)
    settings = tuple(_in_force(entry, setting, values.get(setting.name)) for setting in settings_of(kind))
    return EntrySettings(entry.name, kind, entry.package, entry.version, entry.is_in_code, settings)


def _held_value(tx: Transaction, entry: _Entry, setting: str) -> _Value | None:
    """The operator's row of the entry's setting, locked; None when there has never been one."""
    return tx.fetch_one(_Value, _VALUE_HELD, {"entry_id": entry.id, "setting": setting})


@dataclass(frozen=True)
class _Change:
    """One change asked for: by whom, of which setting of which entry, and whether the environment is protected."""

    caller: Caller
    name: str
    setting: str
    protected: bool


def _refuse_without_a_reason(change: _Change) -> None:
    """Raises `NeedsAReasonError` when a protected environment refuses this change for want of a reason."""
    if change.protected and not (change.caller.context.reason or "").strip():
        raise NeedsAReasonError(change.name)


type _Refusal = NoSuchEntryError | NotInCodeError | NeedsAReasonError | SettingRefusedError
_REFUSALS = (NoSuchEntryError, NotInCodeError, NeedsAReasonError, SettingRefusedError)


def _audit_refusals[T](store: Store, change: _Change, work: Callable[[Transaction], T]) -> T:
    """Runs `work(tx)` for one change; a refusal is rolled back, audited in a transaction of its own, then raised.

    The audit record names the entry and setting, and gives the refusal's words as its reason.
    """
    context = change.caller.context
    try:
        with store.transaction(context) as tx:
            return work(tx)
    except _REFUSALS as refusal:
        _audit_refusal(store, change, refusal)
        raise


def _audit_refusal(store: Store, change: _Change, refusal: _Refusal) -> None:
    """Writes the `refused` audit record of one change."""
    with store.transaction(change.caller.context) as tx:
        tx.refuse(OPERATOR_SETTING, f"{change.name}/{change.setting}", f"{refusal}.")


def _write(tx: Transaction, entry: _Entry, row: _Value | None, setting: str, value: str | None) -> None:
    """Writes the operator's value of the entry's setting: a first row, or the locked one at its version."""
    if row is None:
        tx.insert(OPERATOR_SETTING, {"entry_id": entry.id, "setting": setting, "value": value})
    else:
        tx.update(OPERATOR_SETTING, {"id": row.id}, {"value": value}, row.row_version)


def _set(tx: Transaction, change: _Change, typed: str) -> Changed:
    """Sets the value in `tx`; raises one of the refusals when it cannot be taken."""
    name, setting = change.name, change.setting
    entry = _entry(tx, name, _ENTRY_HELD)
    value = check(Kind(entry.kind), setting, typed)
    if not entry.is_in_code:
        raise NotInCodeError(name)
    row = _held_value(tx, entry, setting)
    if row is not None and row.value == value:
        return Changed(name, setting, value, already=True)
    _refuse_without_a_reason(change)
    _write(tx, entry, row, setting, value)
    return Changed(name, setting, value, already=False)


def set_setting(  # noqa: PLR0913  # who, which entry, which setting, the value, and the environment: all needed
    store: Store, caller: Caller, name: str, setting: str, value: str, *, protected: bool
) -> Changed:
    """Sets the operator's value of `setting` of the entry `name`, for a caller who may change settings.

    The value is kept in its canonical spelling; the same value again writes nothing. Raises
    `NoSuchEntryError`, a `SettingRefusedError` for a setting or value that cannot be taken,
    `NotInCodeError` for an entry no longer in the code, and, when `protected` and the caller's
    context gives no reason, `NeedsAReasonError`; each once the refusal is audited.
    """
    require(store, caller, Action.CHANGE_SETTINGS)
    change = _Change(caller, name, setting, protected)
    return _audit_refusals(store, change, lambda tx: _set(tx, change, value))


def _clear(tx: Transaction, change: _Change) -> Cleared:
    """Clears the value in `tx`; raises one of the refusals when it cannot be done."""
    name, setting = change.name, change.setting
    entry = _entry(tx, name, _ENTRY_HELD)
    known = setting_named(Kind(entry.kind), setting)
    below = _below_the_operator(entry, known)
    row = _held_value(tx, entry, setting)
    if row is None or row.value is None:
        return Cleared(name, setting, had_value=False, in_force=below)
    _refuse_without_a_reason(change)
    _write(tx, entry, row, setting, None)
    return Cleared(name, setting, had_value=True, in_force=below)


def clear_setting(store: Store, caller: Caller, name: str, setting: str, *, protected: bool) -> Cleared:
    """Clears the operator's value of `setting` of the entry `name` (to null, design decision 6).

    Allowed on an entry no longer in the code. Without an operator's value it writes nothing.
    Raises `NoSuchEntryError`, a `SettingRefusedError` for a setting the kind does not have, and,
    when `protected` and the caller's context gives no reason, `NeedsAReasonError` once the
    refusal is audited.
    """
    require(store, caller, Action.CHANGE_SETTINGS)
    change = _Change(caller, name, setting, protected)
    return _audit_refusals(store, change, lambda tx: _clear(tx, change))


def list_operator_values(store: Store, caller: Caller) -> list[OperatorValue]:
    """Every operator's value in the tenant, not cleared, sorted by name then setting; for anyone who may see settings."""
    require(store, caller, Action.SEE_SETTINGS)
    with store.transaction(caller.context) as tx:
        found = tx.fetch_all(_Listed, _LIST)
    return [OperatorValue(row.name, row.setting, row.value, row.is_in_code) for row in found]
