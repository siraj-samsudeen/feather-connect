"""Record blocks: a version's records as one zstd Parquet file (stored-versions, decision 4, ADR 0023)."""

# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyarrow ships no type information; the tests read blocks with it as any other reader would.

import io
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from fcon_server.data.blocks import (
    DELETED,
    ENCRYPTED,
    FORMAT,
    MOVED_FROM,
    PERSON,
    PERSON_KEY,
    BlockFormatError,
    BlockRecord,
    decode_keys,
    decode_records,
    encode_keys,
    encode_records,
)

OLD_SLICE = UUID("01900000-0000-7000-8000-0000000000aa")
ORDERS = [
    BlockRecord({"order_id": 1001, "amount": Decimal("10.00"), "shop": "north"}),
    BlockRecord({"order_id": 1002, "amount": Decimal("12.00"), "shop": "south"}, moved_from=OLD_SLICE),
    BlockRecord({"order_id": 1003, "amount": None, "shop": None}, is_deleted=True),
]


def parquet(data: bytes) -> Any:
    return pq.read_table(io.BytesIO(data))


def written(table: Any) -> bytes:
    sink = io.BytesIO()
    pq.write_table(table, sink)
    return sink.getvalue()


def test_records_come_back_as_they_went_in():
    assert decode_records(encode_records(ORDERS)) == ORDERS


def test_a_decimal_keeps_its_places():
    (record,) = decode_records(encode_records([BlockRecord({"amount": Decimal("12.00")})]))

    assert str(record.fields["amount"]) == "12.00"


def test_decimals_with_different_places_keep_theirs():
    records = [BlockRecord({"amount": Decimal("12.00")}), BlockRecord({"amount": Decimal("1.5")})]

    assert [str(record.fields["amount"]) for record in decode_records(encode_records(records))] == ["12.00", "1.5"]


def test_times_dates_and_flags_keep_their_types():
    record = BlockRecord(
        {"at": datetime(2026, 10, 18, 9, 30, tzinfo=UTC), "on": date(2026, 10, 18), "paid": True, "rate": 0.5}
    )

    assert decode_records(encode_records([record])) == [record]


def test_a_field_with_mixed_types_comes_back_as_it_went_in():
    records = [BlockRecord({"ref": 12}), BlockRecord({"ref": "A-12"}), BlockRecord({"ref": Decimal("1.50")})]

    assert decode_records(encode_records(records)) == records


def test_a_field_with_mixed_types_is_kept_as_json_text_marked_so():
    records = [BlockRecord({"ref": 12}), BlockRecord({"ref": "A-12"})]

    field = parquet(encode_records(records)).schema.field("ref")

    assert (field.type, field.metadata) == (pa.string(), {b"fcon.json": b"1"})


def test_nested_values_come_back_as_they_went_in():
    records = [BlockRecord({"lines": [{"sku": "a", "qty": 1}]}), BlockRecord({"lines": [{"note": "x"}]})]

    assert decode_records(encode_records(records)) == records


def test_a_field_some_records_lack_comes_back_as_null():
    records = [BlockRecord({"order_id": 1, "note": "x"}), BlockRecord({"order_id": 2})]

    assert decode_records(encode_records(records))[1].fields == {"order_id": 2, "note": None}


def test_a_block_is_parquet_compressed_with_zstd():
    metadata = pq.ParquetFile(io.BytesIO(encode_records(ORDERS))).metadata

    assert metadata.row_group(0).column(0).compression == "ZSTD"


def test_a_block_says_its_format():
    assert parquet(encode_records(ORDERS)).schema.metadata[b"fcon.format"] == FORMAT


def test_a_block_has_the_hubs_columns_beside_the_fields():
    table = parquet(encode_records(ORDERS))

    assert (table.column(DELETED).to_pylist(), table.column(MOVED_FROM).to_pylist()) == (
        [False, False, True],
        [None, str(OLD_SLICE), None],
    )


def test_an_empty_block_comes_back_empty():
    assert decode_records(encode_records([])) == []


def test_a_field_named_like_the_hubs_columns_is_refused():
    with pytest.raises(ValueError, match="_fcon_deleted"):
        encode_records([BlockRecord({"_fcon_deleted": 1})])


def test_the_column_reserved_for_the_person_is_refused_as_a_field():
    with pytest.raises(ValueError, match=PERSON):
        encode_records([BlockRecord({PERSON: "person-1"})])


def test_a_block_of_another_format_is_refused():
    table = pa.table({"order_id": [1]}).replace_schema_metadata({b"fcon.format": b"2"})

    with pytest.raises(BlockFormatError, match="format 2"):
        decode_records(written(table))


def test_a_block_with_no_format_is_refused():
    with pytest.raises(BlockFormatError, match="no format"):
        decode_records(written(pa.table({"order_id": [1]})))


def test_data_that_is_not_parquet_is_refused():
    with pytest.raises(BlockFormatError, match="not a Parquet"):
        decode_records(b"not parquet")


def test_a_field_encrypted_per_person_is_refused_with_a_clear_error():
    encrypted = pa.field("email", pa.binary(), metadata={ENCRYPTED: PERSON_KEY})
    schema = pa.schema([encrypted, pa.field(DELETED, pa.bool_())], metadata={b"fcon.format": FORMAT})
    table = pa.Table.from_pylist([{"email": b"\x00", DELETED: False}], schema=schema)

    with pytest.raises(BlockFormatError, match="email is encrypted"):
        decode_records(written(table))


def test_a_key_list_comes_back_as_it_went_in():
    keys = [("1001", bytes(32)), ("1002", bytes(range(32)))]

    assert decode_keys(encode_keys(keys)) == keys


def test_a_key_list_holds_keys_and_fingerprints_only():
    assert parquet(encode_keys([("1001", bytes(32))])).column_names == ["key", "fingerprint"]


def test_a_key_list_of_another_format_is_refused():
    table = pa.table({"key": ["1001"], "fingerprint": [bytes(32)]})

    with pytest.raises(BlockFormatError, match="no format"):
        decode_keys(written(table))
