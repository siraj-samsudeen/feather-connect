"""Steps of the dashboard-basics capability: promises every page keeps."""

from behave import given, then, when

# Whose browser the page to choose a password is opened in: a user with a given password.
NEW_USER = "new user"


@given("the user has switched scripts off in the browser")
def step_scripts_off(context):
    context.world.without_javascript()


@given("the user's computer is set to the {appearance} appearance")
def step_appearance(context, appearance):
    context.world.use_appearance(appearance)


@when("the user opens the sign-in page")
def step_open_sign_in(context):
    context.sign_in_page.open()


@when("the user opens the sign-in page, a refused sign-in and a page that does not exist")
def step_open_three_pages(context):
    page = context.sign_in_page.page
    context.sign_in_page.open()
    context.accessibility.check("the sign-in page", page)
    context.sign_in_page.sign_in("alex", "letmein")
    context.accessibility.check("a refused sign-in", page)
    # Only a signed-in user is told a page does not exist.
    context.sign_in_page.sign_in(*context.user_commands.administrator())
    context.not_found_page.open_missing_run()
    context.accessibility.check("a page that does not exist", page)


@when("the user opens the overview, the page to choose a password and an expired form")
def step_open_signed_in_pages(context):
    page = context.overview.page  # signed in as an administrator by the step before
    context.overview.open()
    context.accessibility.check("the overview", page)
    context.another_site.send_sign_out_form()
    context.accessibility.check("an expired form", page)
    name, password = context.user_commands.new_user()
    context.world.signed_in(NEW_USER, name, password, fresh=True)
    with context.world.on(NEW_USER):
        context.choose_password.open()
        context.accessibility.check("the page to choose a password", context.choose_password.page)


@when("the user opens the address of run 42, which the dashboard does not have")
def step_open_missing_run(context):
    context.not_found_page.open_missing_run()


@then("the page is shown in the {appearance} appearance")
def step_shown_in(context, appearance):
    shown, seen = context.sign_in_page.shown_in(appearance)
    assert shown, "expected the %s appearance; %s" % (appearance, seen)


@then("an automatic accessibility check finds no problem on any of them")
def step_no_accessibility_problem(context):
    problems = context.accessibility.problems()
    assert not problems, "%d accessibility problem(s):\n  %s" % (len(problems), "\n  ".join(problems))


@then("the user is told the page was not found")
def step_told_not_found(context):
    problems = context.not_found_page.not_found_problems()
    assert not problems, "; ".join(problems)


@then("the user can go on to the sign-in page from there")
def step_go_on_to_sign_in(context):
    reached, why = context.not_found_page.go_on_to_sign_in()
    assert reached, why
    named, why = context.sign_in_page.names_the_product()
    assert named, why


@given('the product\'s environment is named "{name}"')
def step_environment_named(context, name):
    context.own_product.start_in_environment(name)


@then('the page names the environment "{name}"')
def step_names_environment(context, name):
    named, why = context.overview.names_environment(name)
    assert named, why
