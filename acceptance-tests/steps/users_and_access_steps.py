"""Steps of the users-and-access capability: users, signing in, and a refused sign-in."""

from behave import given, then, when


@given("the user is not signed in")
def step_not_signed_in(context):
    context.world.signed_out("the user")


@given("nobody has been given access yet")
def step_nobody_has_access(context):
    # The run's database is created empty (support/stack.py), and this change
    # has no way to give anyone access: there is nothing to set up.
    pass


@given('"{name}" is an administrator with the password "{password}"')
def step_administrator(context, name, password):
    context.user_commands.add_administrator(name, password)


@given("a new install with no users")
def step_new_install(context):
    empty, why = context.user_commands.no_users_yet()
    assert empty, why


@when('the operator adds the user "{name}" from the command line, with the password "{password}"')
def step_operator_adds_user(context, name, password):
    context.user_commands.add(name, password)
    ended_well, why = context.user_commands.last_ended_well()
    assert ended_well, why


@when("the user opens the dashboard")
def step_open_dashboard(context):
    context.sign_in_page.open_dashboard()


@when('the user signs in as "{user}" with the password "{password}"')
@when('signs in as "{user}" with the password "{password}"')
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


@then("the user sees the overview")
def step_sees_overview(context):
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@then('the user is shown as "{name}", an {role}')
@then('the user is shown as "{name}", a {role}')
def step_shown_as(context, name, role):
    shown, why = context.overview.shown_as(name, role)
    assert shown, why


# -- the first administrator from a setting ------------------------------------


@given('the product\'s settings name "{name}" as the first administrator')
def step_first_admin_setting(context, name):
    context.first_admin.name_in_settings(name)


@when("the operator starts the product")
def step_operator_starts_product(context):
    context.first_admin.start()


@then('its log gives a one-time password for "{name}", and says to sign in and choose a new one')
def step_log_gives_password(context, name):
    password, why = context.first_admin.one_time_password(name)
    assert password, why
    context.sign_in_page.sign_in(name, password)
    signed_in, why = context.sign_in_page.signed_in()
    assert signed_in, "the password from the log does not sign %r in: %s" % (name, why)


@then("after a restart its log gives no password again")
def step_restart_no_password(context):
    context.first_admin.restart()
    quiet, why = context.first_admin.gives_no_password()
    assert quiet, why


# -- signed in, and where to --------------------------------------------------


@then("the user is still signed in when they open the dashboard again")
def step_still_signed_in(context):
    context.overview.open()
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@when("the user follows a sign-in link that would send them on to another site")
def step_link_to_another_site(context):
    context.sign_in_page.follow_link_to_another_site()


# -- a given password works once ----------------------------------------------


@given('"{name}" was added as an {role} with the first password "{password}"')
@given('"{name}" was added as a {role} with the first password "{password}"')
def step_added_with_given_password(context, name, role, password):
    context.user_commands.add_with_given_password(name, role, password)


@given('the user has signed in as "{user}" with the password "{password}"')
def step_has_signed_in(context, user, password):
    context.sign_in_page.sign_in(user, password)
    signed_in, why = context.sign_in_page.signed_in()
    assert signed_in, why


@given('the user has signed in as "{user}" and chosen the password "{password}"')
def step_has_signed_in_and_chosen(context, user, password):
    context.sign_in_page.sign_in(user, context.user_commands.given_password(user))
    context.choose_password.choose(password)
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@then("the user is asked to choose their own password before going on")
@then("the user is still asked to choose their own password")
def step_asked_to_choose(context):
    problems = context.choose_password.problems()
    assert not problems, "; ".join(problems)


@then('the user sees the overview once they have chosen "{password}"')
def step_overview_once_chosen(context, password):
    context.choose_password.choose(password)
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@when("the user opens the dashboard without choosing a password")
def step_open_without_choosing(context):
    context.sign_in_page.open_dashboard()


@when('the user signs out, and signs in as "{user}" with the password "{password}"')
def step_sign_out_and_in(context, user, password):
    context.overview.sign_out()
    context.sign_in_page.sign_in(user, password)


# -- passwords hard to guess --------------------------------------------------


@when('the user chooses the password "{password}"')
def step_choose_password(context, password):
    context.choose_password.choose(password)


@then("the password is refused, because it is {reason}")
def step_password_refused(context, reason):
    refused, why = context.choose_password.refused_because(reason)
    assert refused, why
