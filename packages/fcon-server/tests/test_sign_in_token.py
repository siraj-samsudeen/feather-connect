"""The sign-in form's own token, against login CSRF (design point 5, § How it
is built): a random value, the time and an HMAC-SHA-256 of both under the
secret key, valid 2 hours; one signed by the previous key is accepted too."""

from datetime import UTC, datetime, timedelta

from fcon_server.signing import SecretKeys, make_sign_in_token, sign_in_token_valid

KEY = "a-test-secret-key-of-32-characters-or-more"
OLD_KEY = "the-previous-secret-key-of-32-characters"
NOW = datetime(2026, 11, 22, 12, 0, tzinfo=UTC)


def test_a_token_just_made_is_valid():
    keys = SecretKeys(KEY)

    assert sign_in_token_valid(keys, make_sign_in_token(keys, NOW), NOW)


def test_each_token_is_new():
    keys = SecretKeys(KEY)

    assert make_sign_in_token(keys, NOW) != make_sign_in_token(keys, NOW)


def test_a_token_is_valid_for_2_hours():
    keys = SecretKeys(KEY)

    assert sign_in_token_valid(keys, make_sign_in_token(keys, NOW), NOW + timedelta(hours=2))


def test_a_token_older_than_2_hours_is_not_valid():
    keys = SecretKeys(KEY)

    assert not sign_in_token_valid(keys, make_sign_in_token(keys, NOW), NOW + timedelta(hours=2, seconds=1))


def test_a_token_from_the_future_is_not_valid():
    keys = SecretKeys(KEY)

    assert not sign_in_token_valid(keys, make_sign_in_token(keys, NOW + timedelta(minutes=5)), NOW)


def test_a_token_signed_by_another_key_is_not_valid():
    assert not sign_in_token_valid(SecretKeys(KEY), make_sign_in_token(SecretKeys(OLD_KEY), NOW), NOW)


def test_a_token_signed_by_the_previous_key_is_valid():
    token = make_sign_in_token(SecretKeys(OLD_KEY), NOW)

    assert sign_in_token_valid(SecretKeys(KEY, previous=OLD_KEY), token, NOW)


def test_a_token_whose_time_was_changed_is_not_valid():
    keys = SecretKeys(KEY)
    value, seconds, signature = make_sign_in_token(keys, NOW).split(".")

    assert not sign_in_token_valid(keys, f"{value}.{int(seconds) + 60}.{signature}", NOW)


def test_text_that_is_not_a_token_is_not_valid():
    assert [sign_in_token_valid(SecretKeys(KEY), text, NOW) for text in ("", "a.b", "a.b.c", "a.1.c.d")] == [
        False,
        False,
        False,
        False,
    ]


def test_the_keys_never_show_in_their_repr():
    assert KEY not in repr(SecretKeys(KEY, previous=OLD_KEY))
