"""Partitions: how a dataset is split into slices, and each slice's row (stored-versions, design decision 10).

A scheme is plain data: its fields in order, each a plain value of a record's field, the `day`
or `month` of a time field in the scheme's time zone, or a `bucket` of the key's SHA-256, never
Python's `hash()`, which changes between runs. From it come a record's slice values, their one
canonical spelling, the slice's start and end in UTC (through `zoneinfo`, so a daylight-saving
day is 23 or 25 hours) and its business name, made each time it is shown. `parse_scheme` and
`parse_slice` read the `fcon data` command's `--by` and `--slice` texts. `ensure_partition`
gets or makes the slice's row in `fcon.partition` through the store.
"""

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta
from typing import Any, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from psycopg.types.json import Jsonb

from fcon_server.store.tables import PARTITION
from fcon_server.store.transaction import Transaction

type Kind = Literal["value", "day", "month", "bucket"]
type Values = dict[str, Any]

ALL = "All"  # the one slice of a dataset with no scheme
_JOIN = " · "
_KINDS: tuple[Kind, ...] = ("value", "day", "month", "bucket")
_WHOLE_NUMBER = re.compile(r"-?\d+")
_MONTH = re.compile(r"\d{4}-\d{2}")


@dataclass(frozen=True)
class Field:
    """One field of a scheme: the slice value's `name`, its `kind`, the record's field it is taken from.

    A `bucket` takes no record field: it is the key's SHA-256 modulo `buckets`.
    """

    name: str
    kind: Kind
    source: str = ""
    buckets: int = 0


@dataclass(frozen=True)
class Scheme:
    """How a dataset is split: its fields in order, and the time zone its days and months are in."""

    fields: tuple[Field, ...] = ()
    time_zone: str = "UTC"


@dataclass(frozen=True)
class Partition:
    """A slice's row: its values, their canonical spelling, its UTC bounds, labels and version counter."""

    id: UUID
    dataset_id: UUID
    values: Values
    values_key: str
    starts_at: datetime | None
    ends_at: datetime | None
    labels: dict[str, str]
    last_version_number: int
    row_version: int


def _local_time(value: object, zone: ZoneInfo) -> datetime:
    """A record's time as a time in `zone`; a time without an offset is taken to be in `zone`."""
    moment = value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=zone)
    return moment.astimezone(zone)


def _bucket(key: str, buckets: int) -> int:
    """The key's bucket: the first 8 bytes of its SHA-256, modulo the count, the same on every run."""
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big") % buckets


def slice_values(scheme: Scheme, record: Mapping[str, object], key: str) -> Values:
    """The values of the slice `record` belongs to, by field name; `{}` for a dataset with no scheme.

    Raises `ValueError` when the record lacks a field the scheme takes its values from.
    """
    zone = ZoneInfo(scheme.time_zone)
    values: Values = {}
    for field in scheme.fields:
        if field.kind == "bucket":
            values[field.name] = _bucket(key, field.buckets)
            continue
        if field.source not in record:
            raise ValueError(f"the record has no {field.source}, which the slice's {field.name} comes from")
        value = record[field.source]
        if field.kind == "day":
            value = _local_time(value, zone).date().isoformat()
        elif field.kind == "month":
            value = f"{_local_time(value, zone):%Y-%m}"
        values[field.name] = value
    return values


def values_key(values: Mapping[str, object]) -> str:
    """The values' one canonical spelling: JSON, keys sorted, no spaces."""
    return json.dumps(values, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _next_month(month: date) -> date:
    """The first day of the month after `month`'s."""
    return date(month.year + month.month // 12, month.month % 12 + 1, 1)


def _utc_midnight(day: date, zone: ZoneInfo) -> datetime:
    """The instant `day` starts in `zone`, in UTC."""
    return datetime(day.year, day.month, day.day, tzinfo=zone).astimezone(UTC)


def slice_bounds(scheme: Scheme, values: Mapping[str, object]) -> tuple[datetime | None, datetime | None]:
    """The slice's start and end in UTC, from its first day or month field; None and None without one."""
    zone = ZoneInfo(scheme.time_zone)
    for field in scheme.fields:
        if field.kind == "day":
            day = date.fromisoformat(str(values[field.name]))
            return _utc_midnight(day, zone), _utc_midnight(day + timedelta(days=1), zone)
        if field.kind == "month":
            month = date.fromisoformat(f"{values[field.name]}-01")
            return _utc_midnight(month, zone), _utc_midnight(_next_month(month), zone)
    return None, None


def _part_name(field: Field, value: object) -> str:
    """One field's part of a business name: "Shop 12", "18 Oct 2026", "Oct 2026", "Bucket 7 of 32"."""
    match field.kind:
        case "day":
            day = date.fromisoformat(str(value))
            return f"{day.day} {day:%b %Y}"
        case "month":
            return f"{date.fromisoformat(f'{value}-01'):%b %Y}"
        case "bucket":
            return f"Bucket {value} of {field.buckets}"
        case _:  # a plain value
            return f"{field.name.replace('_', ' ').capitalize()} {value}"


def business_name(scheme: Scheme, values: Mapping[str, object], labels: Mapping[str, str] | None = None) -> str:
    """The slice's name as a person reads it, its fields' parts in order: "Shop 12 · 18 Oct 2026".

    A label from code for a field replaces that field's part; a dataset with no scheme has "All".
    """
    labels = labels or {}
    parts = [labels.get(field.name) or _part_name(field, values[field.name]) for field in scheme.fields]
    return _JOIN.join(parts) or ALL


def _parse_field(text: str) -> Field:
    """One field of a `--by` text: `shop`, `day:ordered_at`, `month:ordered_at` or `bucket:32`."""
    if ":" not in text:
        return Field(text, "value", text)
    kind, argument = text.split(":", 1)
    if kind not in _KINDS or kind == "value":
        raise ValueError(f"--by: {kind} is not day, month or bucket")
    if kind == "bucket":
        if not argument.isdigit() or int(argument) < 1:
            raise ValueError(f"--by: bucket needs a count of buckets, such as bucket:32, not bucket:{argument}")
        return Field("bucket", "bucket", buckets=int(argument))
    if not argument:
        raise ValueError(f"--by: {kind} needs a time field, such as {kind}:ordered_at")
    return Field(kind, cast(Kind, kind), argument)


def parse_scheme(text: str, time_zone: str = "UTC") -> Scheme:
    """The scheme a `--by` text names, comma-separated, in order; an empty text is no scheme.

    Raises `ValueError`, naming the part, for a text it cannot read or a time zone it does not know.
    """
    try:
        ZoneInfo(time_zone)
    except (ZoneInfoNotFoundError, ValueError) as err:
        raise ValueError(f"--time-zone: {time_zone} is not a time zone, such as Europe/Berlin") from err
    fields = tuple(_parse_field(part.strip()) for part in text.split(",") if part.strip())
    return Scheme(fields, time_zone)


def _typed(field: Field, text: str) -> object:
    """A `--slice` value as the slice keeps it: a whole number as a number, a day or month checked."""
    match field.kind:
        case "day":
            try:
                return date.fromisoformat(text).isoformat()
            except ValueError as err:
                raise ValueError(f"--slice: day={text} is not a date such as 2026-10-18") from err
        case "month":
            if not _MONTH.fullmatch(text):
                raise ValueError(f"--slice: month={text} is not a month such as 2026-10")
            return text
        case "bucket":
            if not text.isdigit() or int(text) >= field.buckets:
                raise ValueError(f"--slice: bucket={text} is not a bucket from 0 to {field.buckets - 1}")
            return int(text)
        case _:  # a plain value
            return int(text) if _WHOLE_NUMBER.fullmatch(text) else text


def parse_slice(scheme: Scheme, text: str) -> Values:
    """The typed values a `--slice` text names, such as `shop=12,day=2026-10-18`, one per scheme field.

    Raises `ValueError`, naming the field, for a field missing, unknown or not readable.
    """
    given: dict[str, str] = {}
    for part in text.split(","):
        name, equals, value = part.strip().partition("=")
        if not equals:
            raise ValueError(f"--slice: {name} needs a value, such as {name}=12")
        given[name] = value
    fields = {field.name: field for field in scheme.fields}
    if unknown := sorted(set(given) - set(fields)):
        raise ValueError(f"--slice: {', '.join(unknown)} is not a field of the scheme")
    if missing := [name for name in fields if name not in given]:
        raise ValueError(f"--slice: {', '.join(missing)} is missing")
    return {name: _typed(field, given[name]) for name, field in fields.items()}


_READ = """
    SELECT id, dataset_id, "values", values_key, starts_at, ends_at, labels, last_version_number, row_version
    FROM fcon.partition
    WHERE tenant_id = %(tenant_id)s AND dataset_id = %(dataset_id)s AND values_key = %(values_key)s
"""


def ensure_partition(
    tx: Transaction,
    dataset_id: UUID,
    scheme: Scheme,
    values: Values,
    labels: Mapping[str, str] | None = None,
) -> Partition:
    """The slice's row for these values, made the first time they are seen (`insert_if_absent`).

    `labels`, when given, are kept as the last ones shown: a slice's labels change when code
    shows others.
    """
    key = values_key(values)
    starts_at, ends_at = slice_bounds(scheme, values)
    row = {"dataset_id": dataset_id, "values": Jsonb(values), "values_key": key}
    row |= {"starts_at": starts_at, "ends_at": ends_at, "labels": Jsonb(dict(labels or {}))}
    tx.insert_if_absent(PARTITION, row)
    partition = tx.fetch_one(Partition, _READ, {"dataset_id": dataset_id, "values_key": key})
    if partition is None:  # pragma: no cover - the row is there: inserted now, or found by the unique rule
        raise LookupError(key)
    if labels is not None and partition.labels != dict(labels):
        update = {"labels": Jsonb(dict(labels))}
        row_version = tx.update(PARTITION, {"id": partition.id}, update, partition.row_version)
        return replace(partition, labels=dict(labels), row_version=row_version)
    return partition
