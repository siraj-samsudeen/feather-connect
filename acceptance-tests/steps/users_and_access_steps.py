"""Steps of the users-and-access capability: users, signing in, and a refused sign-in."""

from behave import given, then, when

from support.world import OTHER_COMPUTER, OTHER_TAB, THE_USER


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


# -- back to the page asked for ------------------------------------------------


@when("the user opens the address of run 42")
def step_open_run_42(context):
    context.not_found_page.open_missing_run()


@then("the user is at the address of run 42")
def step_at_run_42(context):
    there, why = context.not_found_page.at_missing_run()
    assert there, why


# -- signed in, as setup ----------------------------------------------------------


def _signed_in(context, name, who=THE_USER):
    """`who`'s browser, signed in as `name` with a session of its own; the
    user is added as an administrator first unless the scenario added them."""
    if name in context.user_commands.passwords:
        password = context.user_commands.password_of(name)
    else:
        name, password = context.user_commands.administrator(name)
    context.world.signed_in(who, name, password, fresh=True)
    context.signed_in_as = (name, password)


@given('the user is signed in as "{name}"')
@given('the user is signed in as "{name}", an administrator')
def step_signed_in_as(context, name):
    _signed_in(context, name)


@given('"{name}" is an operator with the password "{password}"')
def step_operator_with_own_password(context, name, password):
    context.user_commands.add_with_own_password(name, "operator", password)


# -- signing out ends every session ---------------------------------------------


@given('the user is signed in as "{name}" on two computers')
def step_signed_in_on_two(context, name):
    _signed_in(context, name)
    _signed_in(context, name, OTHER_COMPUTER)


@given('the user has signed in as "{user}" with the password "{password}" on two computers')
def step_has_signed_in_on_two(context, user, password):
    context.world.signed_in(THE_USER, user, password, fresh=True)
    context.world.signed_in(OTHER_COMPUTER, user, password, fresh=True)


@when("the user signs out on one of them")
def step_sign_out_on_one(context):
    context.overview.open()
    context.overview.sign_out()


@when('the user chooses the password "{password}" on one of them')
def step_choose_on_one(context, password):
    context.choose_password.open()
    context.choose_password.choose(password)
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@then("the user is no longer signed in on the other")
def step_signed_out_on_other(context):
    with context.world.on(OTHER_COMPUTER):
        context.sign_in_page.open_dashboard()
        problems = context.sign_in_page.asked_to_sign_in_problems()
    assert not problems, "; ".join(problems)


@when('the operator disables "{name}" from the command line')
def step_operator_disables(context, name):
    context.user_commands.disable(name)


@then("the user is no longer signed in")
def step_no_longer_signed_in(context):
    context.sign_in_page.open_dashboard()
    problems = context.sign_in_page.asked_to_sign_in_problems()
    assert not problems, "%s; the last command: %r" % ("; ".join(problems), context.user_commands.result)


@then('signing in as "{user}" with the password "{password}" is refused')
def step_signing_in_refused(context, user, password):
    context.sign_in_page.sign_in(user, password)
    problems = context.sign_in_page.refusal_problems()
    assert not problems, "; ".join(problems)


# -- sessions run out -----------------------------------------------------------


@when("the user comes back after {hours:d} hours without using the dashboard")
def step_back_after_hours(context, hours):
    context.world.stay_away(hours)
    context.sign_in_page.open_dashboard()


@then("the user is asked to sign in again")
def step_asked_to_sign_in_again(context):
    problems = context.sign_in_page.asked_to_sign_in_problems()
    assert not problems, "; ".join(problems)


# -- guessing is slowed ---------------------------------------------------------


@given('someone has failed to sign in as "{name}" {times:d} times in a row')
def step_someone_failed(context, name, times):
    context.sign_in_page.someone_fails_to_sign_in([name], times)


@given("someone at the user's address has failed to sign in as {count:d} different names")
def step_someone_failed_names(context, count):
    context.sign_in_page.someone_fails_to_sign_in(context.sign_in_page.made_up_names(count))


@when('the user signs in as "{user}" with the password "{password}" at once')
def step_sign_in_at_once(context, user, password):
    context.sign_in_page.sign_in(user, password)


@then("the sign-in is refused, in the same words as a wrong password")
def step_refused_same_words(context):
    problems = context.sign_in_page.refusal_problems() + context.sign_in_page.message_problems()
    assert not problems, "; ".join(problems)


@then('signing in as "{user}" with the password "{password}" works once the wait has passed')
def step_works_after_wait(context, user, password):
    signed_in, why = context.sign_in_page.sign_in_once_the_wait_has_passed(user, password)
    assert signed_in, why
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


# -- forged forms are refused ---------------------------------------------------


@given('the user is signed in as "{name}", with the overview open')
def step_signed_in_overview_open(context, name):
    _signed_in(context, name)
    context.overview.open()
    problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@given("the user has since signed out and back in from another tab")
def step_out_and_in_other_tab(context):
    name, password = context.signed_in_as
    context.world.new_tab(OTHER_TAB)
    with context.world.on(OTHER_TAB):
        context.overview.open()
        context.overview.sign_out()
        context.sign_in_page.sign_in(name, password)
        problems = context.overview.problems()
    assert not problems, "; ".join(problems)


@when("the user signs out from the overview opened before")
def step_sign_out_from_old_overview(context):
    context.overview.press_sign_out()


@then("the user is told the form has expired, and to reload the page")
@then("the form is refused as expired")
def step_form_expired(context):
    problems = context.form_expired.problems()
    assert not problems, "; ".join(problems)


@then("the user can go on to the overview from there")
def step_go_on_to_overview(context):
    problems = context.overview.go_on_from_link()
    assert not problems, "; ".join(problems)


@then("the user is still signed in")
def step_still_signed_in_now(context):
    problems = context.overview.signed_in_problems()
    assert not problems, "; ".join(problems)


@when("a page on another site sends the dashboard a sign-out form")
def step_forged_sign_out(context):
    context.another_site.send_sign_out_form()


# -- the command line, and always an administrator --------------------------------


@when('the operator makes "{name}" an {role} from the command line')
@when('the operator makes "{name}" a {role} from the command line')
def step_operator_sets_role(context, name, role):
    context.user_commands.set_role(name, role)


@when("the user opens the dashboard again")
def step_open_dashboard_again(context):
    context.overview.open()


@given('the operator has disabled "{name}" from the command line')
def step_operator_has_disabled(context, name):
    context.user_commands.disable(name)
    ended_well, why = context.user_commands.last_ended_well()
    assert ended_well, why


@when('the operator enables "{name}" from the command line')
def step_operator_enables(context, name):
    context.user_commands.enable(name)


@given('"{name}" is the only administrator')
def step_only_administrator(context, name):
    context.user_commands.the_only_administrator(name)


@then('the change is refused, because "{name}" is the only administrator')
def step_refused_only_administrator(context, name):
    refused, why = context.user_commands.refused_as_only_administrator(name)
    assert refused, why


@then('"{name}" is still an administrator')
def step_still_administrator(context, name):
    still, why = context.user_commands.is_active_administrator(name)
    assert still, why


# -- every sign-in is recorded ----------------------------------------------------


@then('the audit log records a refused and a successful sign-in for "{name}", from the user\'s address')
def step_audit_sign_ins(context, name):
    problems = context.audit_log.refused_and_successful_sign_in_problems(name)
    assert not problems, "; ".join(problems)


@then("no password appears anywhere in the audit log")
def step_no_password_in_audit(context):
    passwords = context.sign_in_page.typed_passwords + list(context.user_commands.passwords.values())
    problems = context.audit_log.password_problems(passwords)
    assert not problems, "; ".join(problems)
