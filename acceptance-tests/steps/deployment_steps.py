"""Steps of the deployment capability: the product run from its image, as an
operator runs it on a host (pages/container_host.py). "The product answers
that it is ready to take work" is the logs-and-health step, against the
product the scenario started."""

from behave import given, then, when


@given("a new, empty Postgres 18 database")
def step_new_postgres_database(context):
    context.container_host.new_postgres_database()


@given("a host that gives the product the port {port:d}")
def step_host_gives_port(context, port):
    context.container_host.gives_port(port)


@when("the operator upgrades the database with the product's image")
def step_upgrade_with_image(context):
    context.container_host.upgrade_database()
    problems = context.container_host.upgrade_problems()
    assert not problems, "; ".join(problems)


@when("starts the product's image, giving it only the database's address")
def step_start_image(context):
    context.container_host.start_product()


@then("it shows the sign-in page")
def step_shows_sign_in(context):
    context.sign_in_page.open()
    named, why = context.sign_in_page.names_the_product()
    assert named, why
    problems = context.sign_in_page.form_problems()
    assert not problems, "; ".join(problems)


@then("the product answers on port {port:d} that it is running")
def step_answers_running_on_port(context, port):
    reached = context.container_host.product_port()
    assert reached == port, "the scenario reaches the product on its port %d, not %d" % (reached, port)
    context.monitor.check()
    running, answer = context.monitor.says_running()
    assert running, "expected it to say it is running on port %d, got %r" % (port, answer)


@then("the container runtime reports the product as healthy")
def step_reported_healthy(context):
    healthy, why = context.container_host.becomes_healthy()
    assert healthy, why
