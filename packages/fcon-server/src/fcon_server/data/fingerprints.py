"""Fingerprints: whether a record changed, as SHA-256 of one canonical JSON form (stored-versions, decision 11).

Record state keeps each record's fingerprint; reading and sealing compare a record's new one with
it. The form is JSON with keys sorted and no spaces; times in UTC ISO 8601 (a time without an
offset is taken as UTC); dates in ISO 8601; decimals as their own text, unquoted, so `12.00`
stays `12.00` and differs from the string "12.00"; `1` and `1.0` differ. When the dataset
declares a shape, only its fields count.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import cast


def canonical_json(value: object) -> str:
    """The one JSON spelling of `value`: keys sorted, no spaces, times in UTC, decimals as their text.

    Raises `TypeError` for a value with no JSON form, such as a set.
    """
    match value:
        case Mapping():
            fields = {str(key): item for key, item in cast(Mapping[object, object], value).items()}
            members = (f"{json.dumps(key, ensure_ascii=False)}:{canonical_json(fields[key])}" for key in sorted(fields))
            return "{" + ",".join(members) + "}"
        case list() | tuple():
            return "[" + ",".join(canonical_json(item) for item in cast(Sequence[object], value)) + "]"
        case Decimal():
            return str(value)
        case datetime():
            moment = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
            return json.dumps(moment.astimezone(UTC).isoformat())
        case date():
            return json.dumps(value.isoformat())
        case None | bool() | int() | float() | str():
            return json.dumps(value, ensure_ascii=False)
        case _:
            raise TypeError(f"a {type(value).__name__} has no JSON form for a fingerprint")


def fingerprint(record: Mapping[str, object], shape: Sequence[str] | None = None) -> bytes:
    """The record's 32-byte SHA-256 fingerprint, over the shape's fields when one is declared.

    A declared field the record lacks counts as null.
    """
    counted = record if shape is None else {field: record.get(field) for field in shape}
    return hashlib.sha256(canonical_json(counted).encode()).digest()
