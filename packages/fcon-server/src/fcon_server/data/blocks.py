"""Record blocks: a version's records, or a complete read's key list, as one zstd Parquet file.

Stored-versions design decision 4 and ADR 0023. Reading and sealing write a block's bytes to
`fcon.record_block.data`; the snapshot reads them back. Only pyarrow reads or writes them.

- A records block has the records' fields as typed columns, plus the hub's own columns, prefixed
  `_fcon_`: `_fcon_deleted` (the record was deleted at the source) and `_fcon_moved_from` (the
  partition id the record left, or null). A field whose values are not all of one simple type
  (bool, whole number, float, text, decimal of one number of places, time, date), such as
  nested values, is kept as JSON text, its field metadata saying `fcon.json = 1`, and read back
  as it went in. So `12.00` stays `12.00`.
- A key-list block has two columns: `key` and the 32-byte `fingerprint`.
- Every block's key-value metadata says `fcon.format = 1`; a reader refuses another or none.
- Reserved for erasure, not used yet: a personal field encrypted with a person's key will be a
  binary column whose field metadata says `fcon.encrypted = person-key`, beside a
  `_fcon_person` column holding the person's id. Nothing encrypts yet, so a reader refuses such
  a field rather than show its ciphertext.
"""

# pyarrow ships no type information, so pyright cannot follow its calls; this file is the only
# place that uses it, and the tests check every way in and out.
# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false

import io
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq

from fcon_server.data.fingerprints import canonical_json

FORMAT_KEY = b"fcon.format"
FORMAT = b"1"
HUB_PREFIX = "_fcon_"
DELETED = "_fcon_deleted"
MOVED_FROM = "_fcon_moved_from"
JSON_TEXT = {b"fcon.json": b"1"}  # field metadata: the column holds each value as JSON text
ENCRYPTED = b"fcon.encrypted"  # field metadata, reserved for erasure (ADR 0023)
PERSON_KEY = b"person-key"  # ENCRYPTED's value: encrypted with the person's own key
PERSON = "_fcon_person"  # reserved: the person whose key encrypts the row's personal fields
_SIMPLE = (bool, int, float, str, datetime, date)
_COMPRESSION = "zstd"


class BlockFormatError(Exception):
    """A block this version cannot read: not Parquet, another format or none, or an encrypted field."""


@dataclass(frozen=True)
class BlockRecord:
    """One record in a block: its fields, whether it was deleted, and the partition it moved from."""

    fields: dict[str, Any]
    is_deleted: bool = False
    moved_from: UUID | None = None


def _type_of(value: object) -> object:
    """What decides whether two values share a typed column: their type, and a decimal's places."""
    if isinstance(value, Decimal):
        return (Decimal, value.as_tuple().exponent)
    if isinstance(value, datetime):
        return (datetime, value.tzinfo is None)
    return type(value) if isinstance(value, _SIMPLE) else None


def _column(name: str, values: list[Any]) -> tuple[Any, Any]:
    """One field's column: typed when its values share one simple type, else JSON text marked so."""
    types = {_type_of(value) for value in values if value is not None}
    if len(types) <= 1 and None not in types:
        array = pa.array(values)
        return pa.field(name, array.type), array
    texts = [None if value is None else canonical_json(value) for value in values]
    return pa.field(name, pa.string(), metadata=JSON_TEXT), pa.array(texts, pa.string())


def _write(fields: list[Any], arrays: list[Any]) -> bytes:
    """One Parquet file of these columns, compressed with zstd, its metadata saying the format."""
    table = pa.Table.from_arrays(arrays, schema=pa.schema(fields, metadata={FORMAT_KEY: FORMAT}))
    sink = io.BytesIO()
    pq.write_table(table, sink, compression=_COMPRESSION)
    return sink.getvalue()


def encode_records(records: Sequence[BlockRecord]) -> bytes:
    """The records as one block; a field a record lacks is null in its row.

    Raises `ValueError` for a field named like the hub's own columns (`_fcon_…`).
    """
    names = list(dict.fromkeys(name for record in records for name in record.fields))
    if reserved := [name for name in names if name.startswith(HUB_PREFIX)]:
        raise ValueError(f"a record's field may not start with {HUB_PREFIX}: {', '.join(reserved)}")
    columns = [_column(name, [record.fields.get(name) for record in records]) for name in names]
    fields = [field for field, _ in columns] + [pa.field(DELETED, pa.bool_()), pa.field(MOVED_FROM, pa.string())]
    arrays = [array for _, array in columns] + [
        pa.array([record.is_deleted for record in records], pa.bool_()),
        pa.array([None if record.moved_from is None else str(record.moved_from) for record in records], pa.string()),
    ]
    return _write(fields, arrays)


def _read(data: bytes) -> Any:
    """The block's table, once its format is checked; raises `BlockFormatError` for one it cannot read."""
    try:
        table = pq.read_table(io.BytesIO(data))
    except pa.ArrowInvalid as err:
        raise BlockFormatError("the block is not a Parquet file") from err
    found = (table.schema.metadata or {}).get(FORMAT_KEY)
    if found is None:
        raise BlockFormatError("the block says no format; this version reads format 1")
    if found != FORMAT:
        raise BlockFormatError(f"the block is format {found.decode()}; this version reads format 1")
    return table


def _value(field: Any, value: Any) -> Any:
    """A column's value as it went in: JSON text read back, decimals as decimals."""
    if value is not None and field.metadata == JSON_TEXT:
        return json.loads(value, parse_float=Decimal)
    return value


def decode_records(data: bytes) -> list[BlockRecord]:
    """The records of a block, as they went in.

    Raises `BlockFormatError` for a block it cannot read, and for a field encrypted per person,
    which this version cannot decrypt.
    """
    table = _read(data)
    fields = {field.name: field for field in table.schema if field.name not in (DELETED, MOVED_FROM)}
    for field in fields.values():
        if field.metadata and ENCRYPTED in field.metadata:
            raise BlockFormatError(f"the field {field.name} is encrypted per person; this version cannot read it")
    return [
        BlockRecord(
            fields={name: _value(field, row[name]) for name, field in fields.items()},
            is_deleted=row[DELETED],
            moved_from=None if row[MOVED_FROM] is None else UUID(row[MOVED_FROM]),
        )
        for row in table.to_pylist()
    ]


def encode_keys(keys: Sequence[tuple[str, bytes]]) -> bytes:
    """A complete read's key list as one block: each key with its 32-byte fingerprint."""
    fields = [pa.field("key", pa.string()), pa.field("fingerprint", pa.binary(32))]
    arrays = [
        pa.array([key for key, _ in keys], pa.string()),
        pa.array([fingerprint for _, fingerprint in keys], pa.binary(32)),
    ]
    return _write(fields, arrays)


def decode_keys(data: bytes) -> list[tuple[str, bytes]]:
    """The keys and fingerprints of a key-list block; raises `BlockFormatError` for one it cannot read."""
    return [(row["key"], row["fingerprint"]) for row in _read(data).to_pylist()]
