"""Steps of the logs-and-health capability: what a monitor is told."""

from behave import given, then, when

from pages.database_commands import upgrades_of_this_version


@given("the product is running with its database")
def step_running_with_database(context):
    # The run's server: started by environment.py on its own database, and
    # waited for until it said it was ready.
    pass


@given("the product is running")
def step_running(context):
    pass  # as above; the next step may take its database away


@given("its database cannot be reached")
def step_database_unreachable(context):
    context.world.product_without_database()


@when("a monitor checks it")
def step_monitor_checks(context):
    context.monitor.check()


@when("a monitor makes a quick check that asks for no details")
def step_monitor_quick_check(context):
    context.monitor.quick_check()


@then("the product answers that it is running")
def step_answers_running(context):
    running, answer = context.monitor.says_running()
    assert running, "expected it to say it is running, got %r" % answer


@then("the monitor is told the product is running")
def step_told_running(context):
    running, answer = context.monitor.says_running()
    assert running, "expected it to say it is running, got %r" % answer


@given("the product is running on a new, empty database")
def step_running_on_new_database(context):
    context.world.own_database()
    context.world.product_on_own_database()


@given("the product is running on a database that has been upgraded")
def step_running_on_upgraded_database(context):
    context.world.own_database(upgraded=True)
    context.world.product_on_own_database()


@given("the database has one more upgrade, from a newer version")
def step_newer_upgrade(context):
    context.world.add_newer_upgrade()


@then("it answers that it is ready to take work")
@then("the product answers that it is ready to take work")
def step_answers_ready(context):
    ready, answer = context.monitor.becomes_ready()
    assert ready, "expected it to say it is ready, got %r" % answer


@then("the product answers that it is ready to take work, without being restarted")
def step_ready_without_restart(context):
    ready, answer = context.monitor.becomes_ready()
    assert ready, "expected it to say it is ready, got %r" % answer
    assert context.world.scenario_server_still_running(), "the product stopped; it should have stayed up"


@then("it answers that it is not ready, because its database is unavailable")
def step_answers_not_ready(context):
    not_ready, answer = context.monitor.becomes_not_ready_database_unavailable()
    assert not_ready, "expected it to say it is not ready, database unavailable; got %r" % answer


@then("the answer does not say where the database is")
def step_answer_hides_database(context):
    revealed = context.monitor.database_details_revealed(context.world.database)
    assert not revealed, "the replies give the database away: %s" % "; ".join(revealed)


@then("its log says the database is behind, and how to upgrade it")
def step_log_says_behind(context):
    said, why = context.server_log.says_behind(len(upgrades_of_this_version()))
    assert said, "expected the log to say the database is behind, and to run the upgrade; %s" % why


@then("its log names the upgrade that changed, and says to restore it")
def step_log_names_changed(context):
    name = context.world.own_database_state().edited_upgrade
    said, why = context.server_log.says_changed(name)
    assert said, "expected the log to name %s as changed, and to restore it; %s" % (name, why)
