"""Steps of the logs-and-health capability: what a monitor is told."""

from behave import given, then, when


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


@then("it answers that it is ready to take work")
def step_answers_ready(context):
    ready, answer = context.monitor.says_ready()
    assert ready, "expected it to say it is ready, got %r" % answer


@then("it answers that it is not ready, because its database is unavailable")
def step_answers_not_ready(context):
    not_ready, answer = context.monitor.says_not_ready_database_unavailable()
    assert not_ready, "expected it to say it is not ready, database unavailable; got %r" % answer


@then("the answer does not say where the database is")
def step_answer_hides_database(context):
    revealed = context.monitor.database_details_revealed(context.world.database)
    assert not revealed, "the replies give the database away: %s" % "; ".join(revealed)
