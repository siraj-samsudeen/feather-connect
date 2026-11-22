"""Steps of the database-upgrades capability: what the operator is told by
`fcon db upgrade` and `fcon db status` (pages/database_commands.py)."""

from behave import given, then, when


@given("a new, empty database")
def step_new_database(context):
    context.world.own_database()


@given("a database that has been upgraded")
def step_upgraded_database(context):
    context.world.own_database(upgraded=True)


@given("one of its applied upgrades has been edited since it ran")
def step_applied_upgrade_edited(context):
    context.world.edit_an_applied_upgrade()


@when("the operator asks for the database's status")
def step_asks_status(context):
    context.database_commands.status()


@when("the operator upgrades the database")
def step_upgrades(context):
    context.database_commands.upgrade()


@when("the operator starts two upgrades of the database at the same time")
def step_two_upgrades(context):
    context.two_upgrades = context.database_commands.upgrade_twice_at_once()


@then("every upgrade of this version is listed as waiting")
def step_all_waiting(context):
    listed, why = context.database_commands.all_listed_as("waiting")
    assert listed, why


@then("every upgrade of this version is listed as applied, with when it ran")
def step_all_applied(context):
    listed, why = context.database_commands.all_listed_as("applied", with_time=True)
    assert listed, why


@then("none is listed as waiting")
def step_none_waiting(context):
    none, why = context.database_commands.none_listed_as("waiting")
    assert none, why


@then("the operator is told how many upgrades were applied")
def step_told_how_many(context):
    told, why = context.database_commands.told_how_many_applied()
    assert told, why


@then("the database is up to date")
def step_up_to_date(context):
    context.database_commands.status()
    applied, why = context.database_commands.all_listed_as("applied", with_time=True)
    assert applied, why
    none, why = context.database_commands.none_listed_as("waiting")
    assert none, why


@then("the operator is told the database was already up to date")
def step_already_up_to_date(context):
    told, why = context.database_commands.told_already_up_to_date()
    assert told, "expected to be told it was already up to date; %r" % why


@then("both finish without an error")
def step_both_ended_well(context):
    well, bad = context.database_commands.all_ended_well(context.two_upgrades)
    assert well, "an upgrade ended badly:\n%s" % "\n".join(map(repr, bad))


@then("the upgrade is refused")
def step_refused(context):
    refused, why = context.database_commands.refused()
    assert refused, "expected the upgrade to be refused; %r" % why


@then("the operator is told which upgrade changed, and to restore it")
def step_told_which_changed(context):
    name = context.world.own_database_state().edited_upgrade
    told, why = context.database_commands.told_upgrade_changed(name)
    assert told, "expected to be told %s changed, and to restore it; %r" % (name, why)
