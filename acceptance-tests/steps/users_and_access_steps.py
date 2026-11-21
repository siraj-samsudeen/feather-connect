"""Steps of the users-and-access capability: the sign-in page and a refused sign-in."""

from behave import given, then, when


@given("the user is not signed in")
def step_not_signed_in(context):
    context.world.signed_out("the user")


@given("nobody has been given access yet")
def step_nobody_has_access(context):
    # The run's database is created empty (support/stack.py), and this change
    # has no way to give anyone access: there is nothing to set up.
    pass


@when("the user opens the dashboard")
def step_open_dashboard(context):
    context.sign_in_page.open_dashboard()


@when('the user signs in as "{user}" with the password "{password}"')
def step_sign_in(context, user, password):
    context.sign_in_page.sign_in(user, password)


@then("the sign-in page names the product")
def step_names_product(context):
    named, why = context.sign_in_page.names_the_product()
    assert named, why


@then("it asks for the user's name and password, with a button to sign in")
def step_asks_for_name_and_password(context):
    problems = context.sign_in_page.form_problems()
    assert not problems, "; ".join(problems)


@then("the sign-in is refused")
def step_refused(context):
    problems = context.sign_in_page.refusal_problems()
    assert not problems, "; ".join(problems)


@then("the user is told the user name or password is wrong, without being told which")
def step_told_wrong(context):
    problems = context.sign_in_page.message_problems()
    assert not problems, "; ".join(problems)


@then("the page's title says the sign-in failed")
def step_title_failed(context):
    failed, why = context.sign_in_page.title_says_failed()
    assert failed, why
