"""Steps of the stored-data capability: a developer reads orders into a
dataset and follows them with `fcon data` (pages/data_commands.py)."""

from behave import given, register_type, then, when

from pages.data_commands import day_of


# What a scenario writes for a day ('18 Oct 2026'), orders ('1001, 1002 and
# 1003') and an amount ('12.00'); `pattern` is the words behave matches.


def _parse_day(text):
    return day_of(text)


def _parse_ids(text):
    return [int(number) for number in text.replace(" and ", ", ").split(", ")]


def _parse_amount(text):
    return text  # kept as written: 12.00 is compared as the command prints it


_parse_day.pattern = r"\d{1,2} [A-Z][a-z]{2} \d{4}"
_parse_ids.pattern = r"\d+(?:, \d+)*(?: and \d+)?"
_parse_amount.pattern = r"\d+\.\d{2}"
register_type(Day=_parse_day, OrderIds=_parse_ids, Amount=_parse_amount)


# -- the dataset ------------------------------------------------------------


@given("a dataset of orders, split by shop and by day")
def step_dataset(context):
    context.data_commands.give_dataset()


@given("a dataset of orders, split by shop and by day, that allows an empty slice")
def step_dataset_allowing_empty(context):
    context.data_commands.give_dataset(allows_empty=True)


# -- reads ------------------------------------------------------------------


@when("the user reads orders {ids:OrderIds} of shop {shop:d}, ordered on {day:Day}")
def step_reads_orders(context, ids, shop, day):
    context.data_commands.read_orders(ids, shop, day)


@given("the user has read orders {ids:OrderIds} of shop {shop:d}, ordered on {day:Day}")
def step_has_read_orders(context, ids, shop, day):
    context.data_commands.read_orders(ids, shop, day, setup=True)


@given("the user has read orders {ids:OrderIds} of shop {shop:d}, ordered on {day:Day}, each for {amount:Amount}")
def step_has_read_orders_each_for(context, ids, shop, day, amount):
    context.data_commands.read_orders(ids, shop, day, amount=amount, setup=True)


@when("the user reads the same three orders again, with order {order_id:d}'s amount changed")
def step_reads_again_one_changed(context, order_id):
    context.data_commands.read_again(changed=order_id)


@when("the user reads the same three orders again, unchanged")
def step_reads_again_unchanged(context):
    context.data_commands.read_again()


@when(
    "the user reads order {order_id:d} of shop {shop:d}, ordered on {day:Day}, twice in one read,"
    " first with an amount of {first:Amount}, then of {second:Amount}"
)
def step_reads_twice(context, order_id, shop, day, first, second):
    context.data_commands.read_twice_in_one_read(order_id, shop, day, first, second)


@when("the user reads that slice in full, and it returns orders {ids:OrderIds} only")
def step_reads_in_full(context, ids):
    context.data_commands.read_slice_in_full(ids)


@when("the user reads that slice in full, and it returns no orders")
def step_reads_in_full_nothing(context):
    context.data_commands.read_slice_in_full([])


@when("the user reads order {order_id:d} again, now ordered on {day:Day}")
def step_reads_moved(context, order_id, day):
    context.data_commands.read_one_again(order_id, day=day)


@given("the user has read order {order_id:d} again, with its amount changed to {amount:Amount}")
def step_has_read_changed_amount(context, order_id, amount):
    context.data_commands.read_one_again(order_id, amount=amount, setup=True)


# -- what a read said -------------------------------------------------------


@then("the user is told nothing changed")
def step_told_nothing_changed(context):
    told, why = context.data_commands.told_nothing_changed()
    assert told, why


@then("the read is refused, and the user is told the slice would be emptied")
def step_refused_would_empty(context):
    refused, why = context.data_commands.refused_would_empty()
    assert refused, why


# -- versions ---------------------------------------------------------------


@then('the slice "{name}" has {count:d} version')
@then('the slice "{name}" has {count:d} versions')
def step_slice_has_versions(context, name, count):
    context.data_commands.name_slice(name)
    versions, why = context.data_commands.versions(name)
    assert len(versions) == count, "expected %d version(s), found %r; %r" % (count, versions, why)


@then(
    "version {number:d} counts {read:d} records read:"
    " {added:d} added, {changed:d} changed, {deleted:d} deleted and {unchanged:d} unchanged"
)
@then(
    "version {number:d} counts {read:d} record read:"
    " {added:d} added, {changed:d} changed, {deleted:d} deleted and {unchanged:d} unchanged"
)
@then(
    "its version {number:d} counts {read:d} records read:"
    " {added:d} added, {changed:d} changed, {deleted:d} deleted and {unchanged:d} unchanged"
)
@then(
    "its version {number:d} counts {read:d} record read:"
    " {added:d} added, {changed:d} changed, {deleted:d} deleted and {unchanged:d} unchanged"
)
def step_version_counts(context, number, read, added, changed, deleted, unchanged):
    version, why = context.data_commands.version(number)
    expected = (read, added, changed, deleted, unchanged)
    assert version.counts == expected, "expected counts %r, found %r; %r" % (expected, version.counts, why)


@then("version {number:d} holds order {order_id:d} only")
def step_version_holds_only(context, number, order_id):
    version, why = context.data_commands.version(number)
    assert version.record_keys() == [str(order_id)], "version %d holds %r; %r" % (number, version.records, why)


@then("version {number:d} is a complete read")
def step_version_complete(context, number):
    version, why = context.data_commands.version(number)
    assert version.kind == "complete", "version %d is %r; %r" % (number, version.kind, why)


@then("version {first:d} is commit {first_commit:d}, and version {second:d} is commit {second_commit:d}")
def step_versions_commits(context, first, first_commit, second, second_commit):
    for number, commit in ((first, first_commit), (second, second_commit)):
        version, why = context.data_commands.version(number)
        assert version.commit == commit, "version %d is commit %d; %r" % (number, version.commit, why)


# -- following a record -----------------------------------------------------


@when("the user follows order {order_id:d}")
def step_follows(context, order_id):
    context.data_commands.follow(order_id)


@when("the user follows order {order_id:d} as of commit {commit:d}")
def step_follows_as_of(context, order_id, commit):
    context.data_commands.follow(order_id, as_of=commit)


@then("following order {order_id:d} shows an amount of {amount:Amount}")
def step_following_shows_amount(context, order_id, amount):
    context.data_commands.follow(order_id)
    shows, why = context.data_commands.shows_amount(amount)
    assert shows, why


@then("following order {order_id:d} shows it was removed at the source")
def step_following_shows_removed(context, order_id):
    context.data_commands.follow(order_id)
    removed, why = context.data_commands.removed_at_source()
    assert removed, why


@then('following order {order_id:d} shows it in the slice "{name}"')
def step_following_shows_slice(context, order_id, name):
    context.data_commands.follow(order_id)
    shows, why = context.data_commands.shows_slice(name)
    assert shows, why


@then('it shows an amount of {amount:Amount}, in the slice "{name}"')
def step_it_shows_amount_in_slice(context, amount, name):
    shows, why = context.data_commands.shows_amount(amount)
    assert shows, why
    shows, why = context.data_commands.shows_slice(name)
    assert shows, why


@then("it shows an amount of {amount:Amount}")
def step_it_shows_amount(context, amount):
    shows, why = context.data_commands.shows_amount(amount)
    assert shows, why


@then("it was last changed by version {number:d}")
def step_last_changed_by(context, number):
    changed, why = context.data_commands.last_changed_by(number)
    assert changed, why
