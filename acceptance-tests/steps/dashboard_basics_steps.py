"""Steps of the dashboard-basics capability: promises every page keeps."""

from behave import given, then, when


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
    context.not_found_page.open_missing_run()
    context.accessibility.check("a page that does not exist", page)


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
