"""Fingerprints: SHA-256 of one canonical JSON form of a record (stored-versions, design decision 11)."""

import hashlib
from datetime import UTC, date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from fcon_server.data.fingerprints import canonical_json, fingerprint


def test_a_fingerprint_is_the_sha256_of_the_canonical_form():
    record = {"order_id": 1002, "amount": Decimal("12.00")}

    assert fingerprint(record) == hashlib.sha256(canonical_json(record).encode()).digest()


def test_a_fingerprint_is_32_bytes():
    assert len(fingerprint({"order_id": 1})) == 32


def test_the_canonical_form_sorts_keys_without_spaces():
    assert canonical_json({"b": [1, "x"], "a": {"d": None, "c": True}}) == '{"a":{"c":true,"d":null},"b":[1,"x"]}'


def test_the_order_of_the_fields_does_not_change_the_fingerprint():
    assert fingerprint({"a": 1, "b": 2}) == fingerprint({"b": 2, "a": 1})


def test_a_whole_number_and_its_float_differ():
    assert fingerprint({"amount": 1}) != fingerprint({"amount": 1.0})


def test_a_decimal_is_written_as_its_text():
    assert canonical_json({"amount": Decimal("12.00")}) == '{"amount":12.00}'


def test_a_decimal_differs_from_the_same_text_as_a_string():
    assert fingerprint({"amount": Decimal("12.00")}) != fingerprint({"amount": "12.00"})


def test_a_time_is_written_in_utc_iso_8601():
    two_hours_east = datetime(2026, 10, 18, 11, 30, tzinfo=timezone(timedelta(hours=2)))

    assert canonical_json({"at": two_hours_east}) == '{"at":"2026-10-18T09:30:00+00:00"}'


def test_the_same_instant_in_two_zones_has_one_fingerprint():
    in_utc = datetime(2026, 10, 18, 9, 30, tzinfo=UTC)

    assert fingerprint({"at": in_utc}) == fingerprint({"at": in_utc.astimezone(timezone(timedelta(hours=-5)))})


def test_a_time_without_an_offset_is_taken_as_utc():
    assert canonical_json({"at": datetime(2026, 10, 18, 9, 30)}) == '{"at":"2026-10-18T09:30:00+00:00"}'


def test_a_date_is_written_in_iso_8601():
    assert canonical_json({"on": date(2026, 10, 18)}) == '{"on":"2026-10-18"}'


def test_text_is_kept_as_it_is():
    assert canonical_json({"name": "Café"}) == '{"name":"Café"}'


def test_a_shape_limits_the_fingerprint_to_its_fields():
    shape = ["amount"]

    assert fingerprint({"amount": 12, "note": "a"}, shape) == fingerprint({"amount": 12, "note": "b"}, shape)


def test_a_change_to_a_declared_field_changes_the_fingerprint():
    shape = ["amount"]

    assert fingerprint({"amount": 12, "note": "a"}, shape) != fingerprint({"amount": 13, "note": "a"}, shape)


def test_a_declared_field_missing_counts_as_null():
    assert fingerprint({"note": "a"}, ["amount"]) == fingerprint({"amount": None}, ["amount"])


def test_a_value_with_no_json_form_is_refused():
    with pytest.raises(TypeError, match="set"):
        canonical_json({"tags": {"a"}})
