"""Partitions: a dataset's slices, their values, bounds and names (stored-versions, design decision 10)."""

import hashlib
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from fcon_server.data.partitions import (
    Field,
    Scheme,
    business_name,
    ensure_partition,
    parse_scheme,
    parse_slice,
    slice_bounds,
    slice_values,
    values_key,
)
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.transaction import Store

BY_SHOP_AND_DAY = Scheme((Field("shop", "value", "shop"), Field("day", "day", "ordered_at")))
ORDER = {"order_id": 1002, "shop": 12, "ordered_at": "2026-10-18T09:30:00+00:00", "amount": "12.00"}


# -- a record's slice ------------------------------------------------------------------------------


def test_a_plain_field_gives_its_value():
    assert slice_values(Scheme((Field("shop", "value", "shop"),)), ORDER, key="1002") == {"shop": 12}


def test_a_day_is_the_time_fields_date_in_the_schemes_zone():
    late_in_utc = {"ordered_at": "2026-10-18T23:30:00+00:00"}
    in_berlin = Scheme((Field("day", "day", "ordered_at"),), time_zone="Europe/Berlin")

    assert slice_values(in_berlin, late_in_utc, key="1") == {"day": "2026-10-19"}


def test_a_day_is_taken_from_a_datetime_too():
    record = {"ordered_at": datetime(2026, 10, 18, 9, 30, tzinfo=UTC)}

    assert slice_values(Scheme((Field("day", "day", "ordered_at"),)), record, key="1") == {"day": "2026-10-18"}


def test_a_time_without_an_offset_is_in_the_schemes_zone():
    record = {"ordered_at": "2026-10-18T23:30:00"}
    in_new_york = Scheme((Field("day", "day", "ordered_at"),), time_zone="America/New_York")

    assert slice_values(in_new_york, record, key="1") == {"day": "2026-10-18"}


def test_a_month_is_the_time_fields_year_and_month():
    assert slice_values(Scheme((Field("month", "month", "ordered_at"),)), ORDER, key="1") == {"month": "2026-10"}


def test_a_bucket_comes_from_the_sha256_of_the_key():
    expected = int.from_bytes(hashlib.sha256(b"1002").digest()[:8], "big") % 32

    assert slice_values(Scheme((Field("bucket", "bucket", buckets=32),)), ORDER, key="1002") == {"bucket": expected}


def test_a_dataset_with_no_scheme_has_one_slice():
    assert slice_values(Scheme(), ORDER, key="1002") == {}


def test_a_record_without_the_schemes_field_is_refused():
    with pytest.raises(ValueError, match="shop"):
        slice_values(Scheme((Field("shop", "value", "shop"),)), {"order_id": 1}, key="1")


# -- the canonical spelling -----------------------------------------------------------------------


def test_values_are_spelled_with_keys_sorted_and_no_spaces():
    assert values_key({"shop": 12, "day": "2026-10-18"}) == '{"day":"2026-10-18","shop":12}'


def test_values_spelled_alike_whatever_their_order():
    assert values_key({"b": 1, "a": "é"}) == values_key({"a": "é", "b": 1})


# -- the slice's start and end in UTC -------------------------------------------------------------


def test_a_day_runs_from_local_midnight_to_the_next_in_utc():
    in_berlin = Scheme((Field("day", "day", "ordered_at"),), time_zone="Europe/Berlin")

    assert slice_bounds(in_berlin, {"day": "2026-10-18"}) == (
        datetime(2026, 10, 17, 22, tzinfo=UTC),
        datetime(2026, 10, 18, 22, tzinfo=UTC),
    )


def test_the_day_clocks_go_back_lasts_25_hours():
    in_london = Scheme((Field("day", "day", "ordered_at"),), time_zone="Europe/London")

    starts_at, ends_at = slice_bounds(in_london, {"day": "2026-10-25"})

    assert starts_at is not None and ends_at is not None and ends_at - starts_at == timedelta(hours=25)


def test_the_day_clocks_go_forward_lasts_23_hours():
    in_london = Scheme((Field("day", "day", "ordered_at"),), time_zone="Europe/London")

    starts_at, ends_at = slice_bounds(in_london, {"day": "2026-03-29"})

    assert starts_at is not None and ends_at is not None and ends_at - starts_at == timedelta(hours=23)


def test_a_month_runs_from_its_first_local_midnight_to_the_next_months():
    in_london = Scheme((Field("month", "month", "ordered_at"),), time_zone="Europe/London")

    assert slice_bounds(in_london, {"month": "2026-12"}) == (
        datetime(2026, 12, 1, tzinfo=UTC),
        datetime(2027, 1, 1, tzinfo=UTC),
    )


def test_a_slice_with_no_time_field_has_no_bounds():
    assert slice_bounds(Scheme((Field("shop", "value", "shop"),)), {"shop": 12}) == (None, None)


# -- the business name ----------------------------------------------------------------------------


def test_a_slice_is_named_by_its_fields_in_order():
    assert business_name(BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"}) == "Shop 12 · 18 Oct 2026"


def test_a_month_is_named_by_its_month_and_year():
    assert business_name(Scheme((Field("month", "month", "ordered_at"),)), {"month": "2026-10"}) == "Oct 2026"


def test_a_bucket_is_named_with_the_count_of_buckets():
    assert business_name(Scheme((Field("bucket", "bucket", buckets=32),)), {"bucket": 7}) == "Bucket 7 of 32"


def test_a_fields_name_is_capitalised_with_its_underscores_as_spaces():
    scheme = Scheme((Field("sales_region", "value", "sales_region"),))

    assert business_name(scheme, {"sales_region": "north"}) == "Sales region north"


def test_a_label_replaces_the_fields_name_and_value():
    labels = {"shop": "Harbour Street"}

    assert business_name(BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"}, labels) == "Harbour Street · 18 Oct 2026"


def test_a_dataset_with_no_scheme_names_its_slice_all():
    assert business_name(Scheme(), {}) == "All"


# -- the command line's texts ---------------------------------------------------------------------


def test_a_by_text_gives_the_scheme_in_order():
    assert parse_scheme("shop,day:ordered_at") == BY_SHOP_AND_DAY


def test_a_by_text_gives_months_and_buckets():
    assert parse_scheme("month:ordered_at,bucket:32", time_zone="Europe/Berlin") == Scheme(
        (Field("month", "month", "ordered_at"), Field("bucket", "bucket", buckets=32)), time_zone="Europe/Berlin"
    )


def test_an_empty_by_text_is_no_scheme():
    assert parse_scheme("") == Scheme()


@pytest.mark.parametrize(
    ("text", "names"),
    [("week:ordered_at", "week"), ("bucket:none", "bucket"), ("bucket:0", "bucket"), ("day:", "day")],
    ids=["unknown-kind", "bucket-not-a-number", "no-buckets", "no-time-field"],
)
def test_a_by_text_it_cannot_read_is_refused(text: str, names: str):
    with pytest.raises(ValueError, match=names):
        parse_scheme(text)


def test_an_unknown_time_zone_is_refused():
    with pytest.raises(ValueError, match="Mars/Olympus"):
        parse_scheme("day:ordered_at", time_zone="Mars/Olympus")


def test_a_slice_text_gives_typed_values():
    assert parse_slice(BY_SHOP_AND_DAY, "shop=12,day=2026-10-18") == {"shop": 12, "day": "2026-10-18"}


def test_a_slice_text_keeps_a_value_that_is_not_a_number_as_text():
    assert parse_slice(Scheme((Field("shop", "value", "shop"),)), "shop=north") == {"shop": "north"}


def test_a_slice_text_gives_a_month_and_a_bucket():
    scheme = parse_scheme("month:ordered_at,bucket:32")

    assert parse_slice(scheme, "month=2026-10,bucket=7") == {"month": "2026-10", "bucket": 7}


@pytest.mark.parametrize(
    ("text", "names"),
    [
        ("shop=12", "day"),
        ("shop=12,day=2026-10-18,colour=red", "colour"),
        ("shop=12,day=18 Oct", "day"),
        ("shop,day=2026-10-18", "shop"),
    ],
    ids=["a-field-missing", "an-unknown-field", "a-day-not-a-date", "no-equals-sign"],
)
def test_a_slice_text_it_cannot_read_is_refused(text: str, names: str):
    with pytest.raises(ValueError, match=names):
        parse_slice(BY_SHOP_AND_DAY, text)


@pytest.mark.parametrize(
    ("text", "names"),
    [("month=October,bucket=7", "month"), ("month=2026-10,bucket=32", "bucket"), ("month=2026-10,bucket=x", "bucket")],
    ids=["a-month-not-a-month", "a-bucket-out-of-range", "a-bucket-not-a-number"],
)
def test_a_month_or_bucket_it_cannot_read_is_refused(text: str, names: str):
    with pytest.raises(ValueError, match=names):
        parse_slice(parse_scheme("month:ordered_at,bucket:32"), text)


# -- the partition's row --------------------------------------------------------------------------


@pytest.mark.database
def test_a_slice_is_made_once_per_dataset_and_values(store: Store, tenant: Context):
    dataset_id = new_id()
    with store.transaction(tenant) as tx:
        first = ensure_partition(tx, dataset_id, BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"})
        again = ensure_partition(tx, dataset_id, BY_SHOP_AND_DAY, {"day": "2026-10-18", "shop": 12})

    assert again.id == first.id


@pytest.mark.database
def test_a_slice_keeps_its_values_and_utc_bounds(store: Store, tenant: Context):
    in_berlin = Scheme(BY_SHOP_AND_DAY.fields, time_zone="Europe/Berlin")
    with store.transaction(tenant) as tx:
        partition = ensure_partition(tx, new_id(), in_berlin, {"shop": 12, "day": "2026-10-18"})

    assert (partition.values, partition.values_key, partition.starts_at, partition.ends_at) == (
        {"shop": 12, "day": "2026-10-18"},
        '{"day":"2026-10-18","shop":12}',
        datetime(2026, 10, 17, 22, tzinfo=ZoneInfo("UTC")),
        datetime(2026, 10, 18, 22, tzinfo=ZoneInfo("UTC")),
    )


@pytest.mark.database
def test_a_new_slice_has_no_versions_yet(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        partition = ensure_partition(tx, new_id(), Scheme(), {})

    assert partition.last_version_number == 0


@pytest.mark.database
def test_the_same_values_in_another_dataset_are_another_slice(store: Store, tenant: Context):
    with store.transaction(tenant) as tx:
        first = ensure_partition(tx, new_id(), Scheme(), {})
        other = ensure_partition(tx, new_id(), Scheme(), {})

    assert other.id != first.id


@pytest.mark.database
def test_a_slice_keeps_the_labels_last_shown(store: Store, tenant: Context):
    dataset_id = new_id()
    with store.transaction(tenant) as tx:
        ensure_partition(tx, dataset_id, BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"}, {"shop": "Old Street"})
        partition = ensure_partition(
            tx, dataset_id, BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"}, {"shop": "Harbour Street"}
        )

    assert partition.labels == {"shop": "Harbour Street"}


@pytest.mark.database
def test_a_slice_shown_without_labels_keeps_its_own(store: Store, tenant: Context):
    dataset_id = new_id()
    with store.transaction(tenant) as tx:
        ensure_partition(tx, dataset_id, BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"}, {"shop": "Old Street"})
        partition = ensure_partition(tx, dataset_id, BY_SHOP_AND_DAY, {"shop": 12, "day": "2026-10-18"})

    assert partition.labels == {"shop": "Old Street"}


@pytest.mark.database
def test_another_tenants_slice_is_never_reused(store: Store, new_tenant: Callable[[], Context]):
    dataset_id = new_id()
    first_tenant, second_tenant = new_tenant(), new_tenant()
    with store.transaction(first_tenant) as tx:
        first = ensure_partition(tx, dataset_id, Scheme(), {})
    with store.transaction(second_tenant) as tx:
        second = ensure_partition(tx, dataset_id, Scheme(), {})

    assert second.id != first.id
