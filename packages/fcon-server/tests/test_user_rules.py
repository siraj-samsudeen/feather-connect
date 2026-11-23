"""The rules on user names and passwords (design points 2 and 3)."""

import pytest

from fcon_server.users.rules import (
    SHORTEST,
    PasswordProblem,
    UserNameProblem,
    common_passwords,
    normal_name,
    password_problem,
    user_name_problem,
)


def test_a_user_name_is_kept_lowercased():
    assert normal_name("  Ann@Example.COM ") == "ann@example.com"


@pytest.mark.parametrize("name", ["ann", "ben@example.com", "a.b_c-d+e", "x" * 64, "7"])
def test_a_user_name_within_the_rules_is_accepted(name: str):
    assert user_name_problem(name) is None


@pytest.mark.parametrize(
    "name",
    ["", "x" * 65, "ann smith", "ann/1", "ånn", "Ann"],
    ids=["empty", "too-long", "space", "slash", "not-ascii", "uppercase"],
)
def test_a_user_name_outside_the_rules_is_refused(name: str):
    assert user_name_problem(name) is UserNameProblem.NOT_ALLOWED


@pytest.mark.parametrize("password", ["blue-harbour-lamp", "x" * 12, "y" * 128, "çà ünïcode ok"])
def test_a_password_within_the_rules_is_accepted(password: str):
    assert password_problem(password, "ann") is None


def test_a_password_under_12_characters_is_too_short():
    assert password_problem("short-one", "ann") is PasswordProblem.TOO_SHORT


def test_a_password_over_128_characters_is_too_long():
    assert password_problem("x" * 129, "ann") is PasswordProblem.TOO_LONG


def test_a_password_on_the_common_list_is_too_common():
    assert password_problem("password123456", "ann") is PasswordProblem.TOO_COMMON


def test_the_common_list_is_a_starter_list_of_long_passwords():
    listed = common_passwords()

    assert (10 <= len(listed) <= 20, min(map(len, listed))) == (True, SHORTEST)


def test_the_common_list_is_compared_lowercased():
    assert password_problem("PassWord123456", "ann") is PasswordProblem.TOO_COMMON


def test_a_password_that_is_the_users_own_name_is_refused():
    assert password_problem("Ben@Example.com", "ben@example.com") is PasswordProblem.OWN_NAME


def test_each_password_problem_says_which_rule_failed():
    assert {problem.value for problem in PasswordProblem} == {
        "too short",
        "too long",
        "too common",
        "the user's own name",
    }
