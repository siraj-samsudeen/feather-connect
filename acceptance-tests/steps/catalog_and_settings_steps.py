"""Steps of the catalog-and-settings capability: what a developer records with
`fcon catalog record`, and what an operator sees and changes with `fcon
settings` (pages/catalog_commands.py), read back in the audit log
(pages/audit_log.py).

Every quoted value is a Quoted: text with no quote in it, so a step's line
never matches a longer step that starts the same way. A setting the words
name ("look-back", "batch size") is a Words."""

import parse
from behave import given, register_type, then, when

from pages.catalog_commands import SETTING_NAMES


@parse.with_pattern(r'[^"]+')
def _quoted(text):
    return text


@parse.with_pattern(r"[a-z][a-z -]*")
def _words(text):
    return text


@parse.with_pattern(r"the operator|the code|the product's default")
def _who(text):
    return text


register_type(Quoted=_quoted, Words=_words, Who=_who)


def _recorded(context, package_version, **declared):
    result = context.catalog.record(context.catalog.definitions(package_version, **declared))
    assert result.ended_well(), "expected %s to be recorded; %r" % (package_version, result)


def _operator_has_set(context, setting, name, value):
    result = context.catalog.set(name, setting, value)
    assert result.ended_well(), "expected the %s of %s to be set; %r" % (setting, name, result)


# -- Given -----------------------------------------------------------------


@given('the package version "{package_version:Quoted}" declares the flow "{flow:Quoted}", the dataset '
       '"{dataset:Quoted}" and the route "{route:Quoted}"')  # fmt: skip
def step_version_declares(context, package_version, flow, dataset, route):
    context.declared = context.catalog.definitions(package_version)
    names = {item["name"] for kind in ("flows", "datasets", "routes") for item in context.declared[kind]}
    assert {flow, dataset, route} <= names, "the suite's %s declares %r" % (package_version, sorted(names))


@given('"{package_version:Quoted}" has been recorded')
def step_has_been_recorded(context, package_version):
    _recorded(context, package_version)


@given('a protected environment where "{package_version:Quoted}" has been recorded')
def step_protected_recorded(context, package_version):
    context.catalog.use_protected_environment()
    _recorded(context, package_version)


@given('"{package_version:Quoted}" has been recorded, its code giving the dataset "{dataset:Quoted}" a look-back '
       'of "{look_back:Quoted}" and a batch size of "{batch_size:Quoted}"')  # fmt: skip
def step_recorded_look_back_batch(context, package_version, dataset, look_back, batch_size):
    _recorded(context, package_version, dataset_settings={"look-back": look_back, "batch size": batch_size})


@given('"{package_version:Quoted}" has been recorded, its code giving the dataset "{dataset:Quoted}" a look-back '
       'of "{look_back:Quoted}"')  # fmt: skip
def step_recorded_look_back(context, package_version, dataset, look_back):
    _recorded(context, package_version, dataset_settings={"look-back": look_back})


@given('"{package_version:Quoted}" has been recorded, its code giving the dataset "{dataset:Quoted}" no number of tries')
def step_recorded_no_tries(context, package_version, dataset):
    _recorded(context, package_version)


@given('"{package_version:Quoted}" has been recorded, and the operator has set the {setting:Words} of '
       '"{name:Quoted}" to "{value:Quoted}"')  # fmt: skip
def step_recorded_and_set(context, package_version, setting, name, value):
    _recorded(context, package_version)
    _operator_has_set(context, setting, name, value)


@given('the operator has set the {setting:Words} of "{name:Quoted}" to "{value:Quoted}"')
def step_operator_has_set(context, setting, name, value):
    _operator_has_set(context, setting, name, value)


# -- When ------------------------------------------------------------------


@when('the developer records "{package_version:Quoted}"')
def step_records(context, package_version):
    result = context.catalog.record(context.declared)
    assert result.ended_well(), "expected %s to be recorded; %r" % (package_version, result)


@when('the developer records "{package_version:Quoted}" again, with the dataset "{dataset:Quoted}" declared '
      "differently")  # fmt: skip
def step_records_again_differently(context, package_version, dataset):
    context.catalog.record(context.catalog.definitions(package_version, differently=True))


@when('the developer records "{package_version:Quoted}", its code giving "{dataset:Quoted}" a {setting:Words} of '
      '"{value:Quoted}"')  # fmt: skip
def step_records_with_setting(context, package_version, dataset, setting, value):
    _recorded(context, package_version, dataset_settings={setting: value})


@when('the developer records "{package_version:Quoted}", which renames "{old:Quoted}" to "{new:Quoted}"')
def step_records_rename(context, package_version, old, new):
    _recorded(context, package_version, dataset=new.split(".", 1)[1], renamed_from=old)


@when('the developer records "{package_version:Quoted}", which declares "{new:Quoted}" without saying it '
      'replaces "{old:Quoted}"')  # fmt: skip
def step_records_new_name(context, package_version, new, old):
    _recorded(context, package_version, dataset=new.split(".", 1)[1])


@when('the developer records "{package_version:Quoted}", which no longer declares "{old:Quoted}"')
def step_records_without(context, package_version, old):
    _recorded(context, package_version, with_dataset=False)


@when('the operator sets the {setting:Words} of "{name:Quoted}" to "{value:Quoted}"')
def step_sets(context, setting, name, value):
    context.catalog.set(name, setting, value)


@when('the operator sets the {setting:Words} of "{name:Quoted}" to "{value:Quoted}", giving the reason '
      '"{reason:Quoted}"')  # fmt: skip
def step_sets_with_reason(context, setting, name, value, reason):
    context.catalog.set(name, setting, value, reason=reason)


@when('the operator sets the {setting:Words} of "{name:Quoted}" to "{value:Quoted}", giving no reason')
def step_sets_without_reason(context, setting, name, value):
    context.catalog.set(name, setting, value)


@when('the operator looks at the settings of "{name:Quoted}"')
def step_looks_at_settings(context, name):
    context.settings_of = name


@when('the operator clears the {setting:Words} of "{name:Quoted}"')
def step_clears(context, setting, name):
    context.catalog.clear(name, setting)
    why = context.catalog.ended_well()
    assert why is None, "expected the %s of %s to be cleared; %s" % (setting, name, why)


# -- Then ------------------------------------------------------------------


@then('the catalog lists the flow "{flow:Quoted}", the dataset "{dataset:Quoted}" and the route "{route:Quoted}", '
      'each from "{package_version:Quoted}"')  # fmt: skip
def step_catalog_lists(context, flow, dataset, route, package_version):
    why = context.catalog.lists_entries([("flow", flow), ("dataset", dataset), ("route", route)], package_version)
    assert why is None, why


@then("the recording is refused, saying a recorded version never changes and to give the code a new version")
def step_recording_refused(context):
    why = context.catalog.recording_refused_as_changed(context.catalog.recorded_version)
    assert why is None, why


@then('the catalog still has the first definition of "{package_version:Quoted}"')
def step_still_first_definition(context, package_version):
    why = context.catalog.recorded_already_unchanged(package_version)
    assert why is None, "expected the first definitions to be the recorded ones; %s" % why


@then('the settings of "{name:Quoted}" show the {setting:Words} "{value:Quoted}", set by {who:Who}')
def step_settings_show(context, name, setting, value, who):
    context.settings_of = name
    why = context.catalog.shows_setting(name, setting, value, who)
    assert why is None, why


@then('the settings of "{name:Quoted}" still show the {setting:Words} "{value:Quoted}", set by {who:Who}')
def step_settings_still_show(context, name, setting, value, who):
    why = context.catalog.shows_setting(name, setting, value, who)
    assert why is None, why


@then('they show the {setting:Words} "{value:Quoted}", set by {who:Who}')
def step_they_show(context, setting, value, who):
    why = context.catalog.shows_setting(context.settings_of, setting, value, who)
    assert why is None, why


@then('the settings of "{name:Quoted}" show no value set by the operator')
def step_no_operator_value(context, name):
    values, shown = context.catalog.operator_values_shown(name)
    assert not values, "expected no value set by the operator, got %r\n%s" % (values, shown)


@then('the catalog no longer lists "{name:Quoted}"')
def step_no_longer_lists(context, name):
    listed, shown = context.catalog.lists_name(name)
    assert not listed, "expected %s not to be listed\n%s" % (name, shown)


@then('the recording warns that the operator\'s {setting:Words} of "{name:Quoted}" is for a name the code no '
      "longer has")  # fmt: skip
def step_recording_warns(context, setting, name):
    why = context.catalog.recording_warned(name, setting)
    assert why is None, why


@then('the list of every value operators have set shows the {setting:Words} "{value:Quoted}" of "{name:Quoted}", '
      "flagged as no longer in the code")  # fmt: skip
def step_list_flags(context, setting, value, name):
    why = context.catalog.operator_value_flagged(name, setting, value)
    assert why is None, why


@then("the change is refused, saying the key is decided by the code, and naming the settings a dataset has")
def step_refused_code_decides(context):
    why = context.catalog.refused_as_code_decided(context.catalog.last_set[0], "key")
    assert why is None, why


@then('the change is refused, saying a look-back is a length of time such as "{first:Quoted}" or "{second:Quoted}"')
def step_refused_not_a_look_back(context, first, second):
    why = context.catalog.refused_as_not_a_look_back(context.catalog.last_set[2])
    assert why is None, why


@then("the change is refused, saying a protected environment needs a reason for every change")
def step_refused_no_reason(context):
    why = context.catalog.refused_for_no_reason(context.catalog.last_set[0])
    assert why is None, why


@then('the audit log records the change of the {setting:Words} of "{name:Quoted}" to "{value:Quoted}", by the '
      'operator, with the reason "{reason:Quoted}"')  # fmt: skip
def step_audit_change(context, setting, name, value, reason):
    why = context.audit_log.setting_change_problems(SETTING_NAMES[setting], value, reason)
    assert why is None, why


@then("the audit log records the refusal")
def step_audit_refusal(context):
    name, setting, _ = context.catalog.last_set
    why = context.audit_log.setting_refusal_problems(name, setting, context.catalog.refusal_text(name))
    assert why is None, why
