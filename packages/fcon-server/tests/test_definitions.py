"""Reading one package version's definitions (design § How it is built, A definitions file).

Every name, version and code value is checked at the edge; what the code decides is kept whole.
"""

import json
from typing import Any

import pytest

from fcon_server.catalog.definitions import (
    LARGEST,
    CodeValueError,
    NotDefinitionsError,
    parse_definitions,
    read_definitions,
)
from fcon_server.catalog.known_settings import BadValueError, DecidedByCodeError, Kind, UnknownSettingError


def shop(**changes: Any) -> dict[str, Any]:
    """The example package version of the contract, with `changes` to its top-level keys."""
    return {
        "package": "shop-flows",
        "version": "1.0",
        "flows": [{"name": "shop-flows.daily", "settings": {"schedule": "0 6 * * *"}}],
        "datasets": [
            {
                "name": "shop-flows.orders",
                "source": "shop-api.orders",
                "key": ["order_id"],
                "settings": {"look-back": "1d", "batch-size": 5000},
            }
        ],
        "routes": [{"name": "shop-flows.orders-to-crm", "dataset": "shop-flows.orders", "write_mode": "upsert"}],
        **changes,
    }


def refusal(data: object) -> NotDefinitionsError:
    with pytest.raises(NotDefinitionsError) as refused:
        read_definitions(data)
    return refused.value


def test_the_package_and_version_are_read():
    read = read_definitions(shop())

    assert (read.package, read.version) == ("shop-flows", "1.0")


def test_each_item_is_read_with_its_kind_in_order():
    assert [(each.kind, each.name) for each in read_definitions(shop()).definitions] == [
        (Kind.FLOW, "shop-flows.daily"),
        (Kind.DATASET, "shop-flows.orders"),
        (Kind.ROUTE, "shop-flows.orders-to-crm"),
    ]


def test_what_the_code_decides_is_kept_whole():
    route = read_definitions(shop()).definitions[2]

    assert route.body == {"name": "shop-flows.orders-to-crm", "dataset": "shop-flows.orders", "write_mode": "upsert"}


def test_the_codes_values_are_kept_in_their_canonical_spelling():
    dataset = read_definitions(shop()).definitions[1]

    assert dataset.settings == {"look-back": "1d", "batch-size": "5000"}


def test_the_body_holds_the_codes_values_in_their_canonical_spelling():
    data = shop(datasets=[{"name": "shop-flows.orders", "settings": {"look-back": "01d"}}])

    assert read_definitions(data).definitions[1].body["settings"] == {"look-back": "1d"}


def test_every_list_may_be_left_out():
    assert read_definitions({"package": "shop-flows", "version": "1.0"}).definitions == ()


def test_a_rename_names_the_old_name():
    data = shop(datasets=[{"name": "shop-flows.sales-orders", "renamed_from": "shop-flows.orders"}])

    assert read_definitions(data).definitions[1].renamed_from == "shop-flows.orders"


def test_an_item_with_no_rename_has_none():
    assert read_definitions(shop()).definitions[0].renamed_from is None


def test_the_same_definitions_have_the_same_checksum():
    assert read_definitions(shop()).checksum == read_definitions(json.loads(json.dumps(shop()))).checksum


def test_the_checksum_does_not_depend_on_the_order_of_keys():
    reordered = dict(reversed(list(shop().items())))

    assert read_definitions(reordered).checksum == read_definitions(shop()).checksum


def test_the_checksum_does_not_depend_on_how_a_value_is_spelled():
    spelled = shop(datasets=[{"name": "shop-flows.orders", "settings": {"look-back": "01d"}}])
    canonical = shop(datasets=[{"name": "shop-flows.orders", "settings": {"look-back": "1d"}}])

    assert read_definitions(spelled).checksum == read_definitions(canonical).checksum


def test_other_definitions_have_another_checksum():
    changed = shop(datasets=[{"name": "shop-flows.orders", "key": ["order_number"]}])

    assert read_definitions(changed).checksum != read_definitions(shop()).checksum


def test_the_checksum_is_a_sha256():
    assert len(read_definitions(shop()).checksum) == 64


def test_a_file_is_read_as_utf8_json():
    assert parse_definitions(json.dumps(shop()).encode()).package == "shop-flows"


def test_a_file_larger_than_the_limit_is_refused():
    with pytest.raises(NotDefinitionsError) as refused:
        parse_definitions(b" " * (LARGEST + 1))

    assert refused.value.what == "it is larger than 1 MB"


def test_a_file_that_is_not_json_is_refused():
    with pytest.raises(NotDefinitionsError) as refused:
        parse_definitions(b'{"package": ')

    assert refused.value.what.startswith("it is not JSON")


def test_a_file_that_is_not_utf8_is_refused():
    with pytest.raises(NotDefinitionsError) as refused:
        parse_definitions(b'{"package": "\xff"}')

    assert refused.value.what == "it is not UTF-8"


def test_json_that_is_not_an_object_is_refused():
    assert refusal(["shop-flows"]).what == "it is not a JSON object"


def test_an_unknown_top_level_key_is_refused():
    assert refusal(shop(connections=[])).what == 'it has an unknown key "connections"'


@pytest.mark.parametrize("package", ["Shop", "1shop", "", "shop_flows", "s" * 65, 7, None])
def test_a_package_name_that_breaks_the_rule_is_refused(package: object):
    assert refusal(shop(package=package)).expected == (
        "A package name is 1 to 64 of a-z, 0-9 and -, starting with a letter."
    )


@pytest.mark.parametrize("version", ["", "1 0", "v" * 65, "1.0\n", 1.0])
def test_a_version_that_breaks_the_rule_is_refused(version: object):
    assert refusal(shop(version=version)).expected == "A version is 1 to 64 printable characters, no spaces."


def test_a_list_that_is_not_one_is_refused():
    assert refusal(shop(flows={"name": "shop-flows.daily"})).what == "flows is not a list"


def test_an_item_that_is_not_an_object_is_refused():
    assert refusal(shop(routes=["shop-flows.orders-to-crm"])).what == "an item of routes is not an object"


@pytest.mark.parametrize(
    "name", ["orders", "other.orders", "shop-flows.Orders", "shop-flows.", "shop-flows.1st", "shop-flows.a.b", None]
)
def test_a_name_that_does_not_carry_the_packages_name_is_refused(name: object):
    data = shop(datasets=[{"name": name}])

    assert refusal(data).expected == "A name is shop-flows. then 1 to 64 of a-z, 0-9, - and _, starting with a letter."


def test_a_name_declared_twice_is_refused():
    data = shop(routes=[{"name": "shop-flows.orders"}])

    assert refusal(data).what == "shop-flows.orders is declared twice"


def test_a_rename_from_another_package_is_refused():
    data = shop(datasets=[{"name": "shop-flows.sales-orders", "renamed_from": "other-flows.orders"}])

    assert refusal(data).what == (
        "shop-flows.sales-orders is renamed from other-flows.orders, which is not a name of shop-flows"
    )


def test_a_rename_whose_old_name_is_still_declared_is_refused():
    data = shop(
        datasets=[
            {"name": "shop-flows.orders"},
            {"name": "shop-flows.sales-orders", "renamed_from": "shop-flows.orders"},
        ]
    )

    assert refusal(data).what == (
        "shop-flows.sales-orders is renamed from shop-flows.orders, which this version still declares"
    )


def test_settings_that_are_not_an_object_are_refused():
    data = shop(datasets=[{"name": "shop-flows.orders", "settings": ["look-back"]}])

    assert refusal(data).what == "the settings of shop-flows.orders are not an object"


@pytest.mark.parametrize("value", [True, 1.5, None, ["1d"]])
def test_a_code_value_that_is_not_a_text_or_a_whole_number_is_refused(value: object):
    data = shop(datasets=[{"name": "shop-flows.orders", "settings": {"look-back": value}}])

    assert refusal(data).what == "the look-back of shop-flows.orders is not a text or a whole number"


def code_value_refusal(settings: dict[str, object]) -> CodeValueError:
    with pytest.raises(CodeValueError) as refused:
        read_definitions(shop(datasets=[{"name": "shop-flows.orders", "settings": settings}]))
    return refused.value


def test_a_wrong_code_value_is_refused_naming_the_entry():
    refused = code_value_refusal({"look-back": "three days"})

    assert (refused.name, type(refused.refused)) == ("shop-flows.orders", BadValueError)


def test_an_unknown_setting_in_the_code_is_refused():
    assert isinstance(code_value_refusal({"colour": "blue"}).refused, UnknownSettingError)


def test_a_code_decided_name_among_the_settings_is_refused():
    assert isinstance(code_value_refusal({"key": "order_id"}).refused, DecidedByCodeError)
