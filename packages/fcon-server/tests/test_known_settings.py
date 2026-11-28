"""The settings an operator owns, per kind, each with its type and default (design decision 5).

One parser per type gives a value's canonical spelling, or says what is expected.
"""

import pytest

from fcon_server.catalog.known_settings import (
    BadValueError,
    DecidedByCodeError,
    Kind,
    UnknownSettingError,
    check,
    settings_of,
)


def names(kind: Kind) -> list[str]:
    return [setting.name for setting in settings_of(kind)]


def test_a_datasets_settings_are_listed_in_order():
    assert names(Kind.DATASET) == [
        "look-back",
        "full-comparison-schedule",
        "batch-size",
        "tries",
        "time-limit",
        "readiness-interval",
        "late-data",
        "schema-changes",
        "alert-when-stale-after",
        "keep-records",
        "keep-versions",
        "fetch-batch-size",
        "fetch-tries",
        "fetch-time-limit",
    ]


def test_a_flows_settings_are_listed_in_order():
    assert names(Kind.FLOW) == [
        "on",
        "schedule",
        "time-zone",
        "paused-until",
        "tries",
        "time-limit",
        "parallel-work",
        "overlap",
        "catch-up",
        "alert-after-failures",
    ]


def test_a_routes_settings_are_listed_in_order():
    assert names(Kind.ROUTE) == [
        "on",
        "paused-until",
        "tries",
        "time-limit",
        "batch-size",
        "parallel-partitions",
        "approval",
        "supersede-automatically",
        "parent-wait-limit",
        "alert-after-failures",
        "keep-deliveries",
        "keep-answers",
    ]


@pytest.mark.parametrize(
    ("kind", "setting", "default"),
    [
        (Kind.FLOW, "on", "off"),
        (Kind.ROUTE, "on", "on"),
        (Kind.DATASET, "tries", "6"),
        (Kind.DATASET, "look-back", "0s"),
        (Kind.FLOW, "schedule", "none"),
        (Kind.FLOW, "time-zone", "UTC"),
        (Kind.DATASET, "keep-versions", "400d"),
    ],
)
def test_a_setting_has_the_products_default(kind: Kind, setting: str, default: str):
    assert {each.name: each.default for each in settings_of(kind)}[setting] == default


@pytest.mark.parametrize("kind", list(Kind))
def test_every_default_is_a_value_of_its_settings_type(kind: Kind):
    for setting in settings_of(kind):
        assert check(kind, setting.name, setting.default) == setting.default


@pytest.mark.parametrize(
    ("setting", "typed", "canonical"),
    [
        ("look-back", "3d", "3d"),
        ("look-back", "12h", "12h"),
        ("look-back", "15m", "15m"),
        ("look-back", "90s", "90s"),
        ("look-back", "007d", "7d"),
        ("look-back", " 3d ", "3d"),
    ],
)
def test_a_length_of_time_is_spelled_canonically(setting: str, typed: str, canonical: str):
    assert check(Kind.DATASET, setting, typed) == canonical


@pytest.mark.parametrize("typed", ["three days", "3", "3 d", "3D", "-1d", "1w", "", "1.5h"])
def test_a_length_of_time_in_another_form_is_refused(typed: str):
    with pytest.raises(BadValueError):
        check(Kind.DATASET, "look-back", typed)


def test_a_wrong_value_says_what_is_expected():
    with pytest.raises(BadValueError) as refused:
        check(Kind.DATASET, "look-back", "three days")

    assert (refused.value.value, refused.value.setting, refused.value.expected) == (
        "three days",
        "look-back",
        "A look-back is a length of time, such as 3d or 12h.",
    )


@pytest.mark.parametrize(("typed", "canonical"), [("5000", "5000"), ("1", "1"), ("0100", "100")])
def test_a_count_is_spelled_canonically(typed: str, canonical: str):
    assert check(Kind.DATASET, "batch-size", typed) == canonical


@pytest.mark.parametrize("typed", ["0", "-5", "many", "5e3", "1.0"])
def test_a_count_below_its_least_or_not_whole_is_refused(typed: str):
    with pytest.raises(BadValueError):
        check(Kind.DATASET, "batch-size", typed)


def test_a_count_may_start_from_nought():
    assert check(Kind.DATASET, "tries", "1") == "1"


def test_a_count_says_its_least_value():
    with pytest.raises(BadValueError) as refused:
        check(Kind.DATASET, "batch-size", "0")

    assert refused.value.expected == "A batch-size is a whole number from 1 up."


@pytest.mark.parametrize("typed", ["on", "off"])
def test_on_or_off_is_taken(typed: str):
    assert check(Kind.ROUTE, "supersede-automatically", typed) == typed


@pytest.mark.parametrize("typed", ["yes", "true", "ON", "1"])
def test_anything_but_on_or_off_is_refused_for_a_switch(typed: str):
    with pytest.raises(BadValueError):
        check(Kind.ROUTE, "supersede-automatically", typed)


def test_no_tries_at_all_is_refused():
    with pytest.raises(BadValueError):
        check(Kind.DATASET, "tries", "0")


def test_a_choice_from_its_set_is_taken():
    assert check(Kind.FLOW, "overlap", "queue") == "queue"


def test_a_choice_outside_its_set_says_the_set():
    with pytest.raises(BadValueError) as refused:
        check(Kind.FLOW, "overlap", "sometimes")

    assert refused.value.expected == "An overlap is one of queue, skip or cancel."


@pytest.mark.parametrize(
    ("kind", "setting", "expected"),
    [
        (Kind.DATASET, "late-data", "A late-data is one of run-again, warn or ignore."),
        (Kind.ROUTE, "approval", "An approval is one of never, always or per-record."),
        (Kind.FLOW, "catch-up", "A catch-up is one of latest, each or none."),
    ],
)
def test_a_choices_set_is_the_designs(kind: Kind, setting: str, expected: str):
    with pytest.raises(BadValueError) as refused:
        check(kind, setting, "sometimes")

    assert refused.value.expected == expected


@pytest.mark.parametrize(
    ("kind", "setting", "default"),
    [
        (Kind.DATASET, "late-data", "warn"),
        (Kind.ROUTE, "approval", "never"),
        (Kind.FLOW, "catch-up", "latest"),
        (Kind.FLOW, "overlap", "skip"),
    ],
)
def test_a_choices_default_is_the_designs(kind: Kind, setting: str, default: str):
    assert {each.name: each.default for each in settings_of(kind)}[setting] == default


@pytest.mark.parametrize("typed", ["UTC", "Europe/Paris", "America/New_York"])
def test_a_time_zone_is_taken(typed: str):
    assert check(Kind.FLOW, "time-zone", typed) == typed


@pytest.mark.parametrize("typed", ["Mars/Olympus", "America", "../etc/passwd", "/etc/localtime", "utc ", "", "none"])
def test_anything_but_a_time_zone_is_refused(typed: str):
    with pytest.raises(BadValueError):
        check(Kind.FLOW, "time-zone", typed)


@pytest.mark.parametrize(
    ("typed", "canonical"),
    [("0 6 * * *", "0 6 * * *"), ("*/15  8-18 * * 1-5", "*/15 8-18 * * 1-5"), ("0,30 * * * *", "0,30 * * * *")],
)
def test_a_schedule_is_five_cron_fields_spelled_canonically(typed: str, canonical: str):
    assert check(Kind.FLOW, "schedule", typed) == canonical


@pytest.mark.parametrize("typed", ["0 6 * *", "0 6 * * * *", "daily", "0 6 * * MON", ""])
def test_anything_but_five_cron_fields_is_refused_for_a_schedule(typed: str):
    with pytest.raises(BadValueError):
        check(Kind.FLOW, "schedule", typed)


def test_none_is_taken_where_a_setting_may_have_no_value():
    assert check(Kind.FLOW, "schedule", "none") == "none"


def test_none_is_refused_where_a_setting_needs_a_value():
    with pytest.raises(BadValueError):
        check(Kind.DATASET, "look-back", "none")


def test_a_setting_that_may_have_no_value_says_so():
    with pytest.raises(BadValueError) as refused:
        check(Kind.FLOW, "schedule", "daily")

    assert refused.value.expected == "A schedule is five cron fields, such as 0 6 * * *, or none."


@pytest.mark.parametrize(
    ("typed", "canonical"),
    [
        ("2026-12-01T06:00+00:00", "2026-12-01T06:00:00+00:00"),
        ("2026-12-01T06:00:00+01:00", "2026-12-01T06:00:00+01:00"),
        ("2026-12-01T06:00Z", "2026-12-01T06:00:00+00:00"),
    ],
)
def test_a_time_with_its_offset_is_spelled_canonically(typed: str, canonical: str):
    assert check(Kind.FLOW, "paused-until", typed) == canonical


@pytest.mark.parametrize("typed", ["2026-12-01T06:00", "tomorrow", "2026-13-01T06:00+00:00"])
def test_a_time_without_its_offset_is_refused(typed: str):
    with pytest.raises(BadValueError):
        check(Kind.FLOW, "paused-until", typed)


@pytest.mark.parametrize("setting", ["key", "source", "write-mode", "write_mode", "partition-scheme"])
def test_a_name_the_code_decides_is_refused_as_decided_by_the_code(setting: str):
    with pytest.raises(DecidedByCodeError) as refused:
        check(Kind.DATASET, setting, "order_number")

    assert (refused.value.kind, refused.value.setting) == (Kind.DATASET, setting)


def test_a_setting_the_kind_does_not_have_is_unknown():
    with pytest.raises(UnknownSettingError) as refused:
        check(Kind.DATASET, "colour", "blue")

    assert (refused.value.kind, refused.value.setting) == (Kind.DATASET, "colour")


def test_a_setting_of_another_kind_is_unknown():
    with pytest.raises(UnknownSettingError):
        check(Kind.DATASET, "schedule", "0 6 * * *")
