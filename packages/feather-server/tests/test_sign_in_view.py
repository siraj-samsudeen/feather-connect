"""What the sign-in page shows, as computed for its template."""

from feather_server.pages import REFUSAL, sign_in_view


def test_the_sign_in_page_is_titled_for_signing_in():
    assert sign_in_view().title == "Sign in – Feather Connect"


def test_the_sign_in_page_shows_no_alert_before_a_sign_in():
    assert sign_in_view().alerts == ()


def test_the_fields_are_not_marked_invalid_before_a_sign_in():
    view = sign_in_view()

    assert [field.get("aria-invalid") for field in (view.user_field, view.password_field)] == [None, None]


def test_a_refused_sign_in_says_the_user_name_or_password_is_wrong():
    view = sign_in_view("alex", refused=True)

    assert [alert.text for alert in view.alerts] == [REFUSAL]


def test_a_refused_sign_in_links_its_alert_to_the_form():
    view = sign_in_view("alex", refused=True)

    assert view.form["aria-describedby"] == view.alerts[0].id


def test_a_refused_sign_in_marks_both_fields_invalid():
    view = sign_in_view("alex", refused=True)

    assert [field.get("aria-invalid") for field in (view.user_field, view.password_field)] == ["true", "true"]


def test_a_refused_sign_in_is_titled_as_failed():
    assert sign_in_view("alex", refused=True).title == "Sign-in failed – Feather Connect"


def test_a_refused_sign_in_keeps_the_user_name_typed():
    assert sign_in_view("alex", refused=True).user_field["value"] == "alex"


def test_the_password_field_never_holds_a_value():
    assert "value" not in sign_in_view("alex", refused=True).password_field
