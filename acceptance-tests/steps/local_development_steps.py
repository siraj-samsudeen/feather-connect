"""Steps of the local-development capability: starting the server from a terminal."""

from behave import given, then, when


@given("no database address has been set")
def step_no_database_address(context):
    context.terminal.without_database_address()


@given("another program is using the server's port (the number it listens on)")
def step_port_taken(context):
    context.terminal.port_held_by_another_program()


@when("the user starts the server")
def step_start_server(context):
    context.terminal.start_server()


@then("the server does not start")
def step_server_does_not_start(context):
    stopped, why = context.terminal.server_did_not_start()
    assert stopped, why


@then("it says the database address is missing, and how to set it")
def step_says_address_missing(context):
    said, why = context.terminal.says_database_address_missing()
    assert said, "expected it to say the database address is missing, and how to set it: %s" % why


@then("it names the port, and says how to choose another")
def step_names_port(context):
    said, why = context.terminal.names_taken_port()
    assert said, "expected it to name the port, and say how to choose another: %s" % why
