"""User names and passwords (design points 2 and 3). A name is lowercase
letters, digits and `. _ - @ +`, 1 to 64 characters, so an email address
works; it is stored lowercased. A password is 12 to 128 characters of any
kind, with no composition rules, and neither one of the most common
passwords nor the user's own name. A problem says which rule failed."""

import re
from enum import StrEnum
from functools import cache
from importlib.resources import files

NAME = re.compile(r"[a-z0-9._@+-]{1,64}")
SHORTEST = 12
LONGEST = 128
COMMON_LIST = "common_passwords.txt"


class UserNameProblem(StrEnum):
    NOT_ALLOWED = "not allowed"


class PasswordProblem(StrEnum):
    TOO_SHORT = "too short"
    TOO_LONG = "too long"
    TOO_COMMON = "too common"
    OWN_NAME = "the user's own name"


def normal_name(typed: str) -> str:
    """The name as stored: without surrounding spaces, lowercased."""
    return typed.strip().lower()


def user_name_problem(name: str) -> UserNameProblem | None:
    """For a name already made normal (`normal_name`)."""
    return None if NAME.fullmatch(name) else UserNameProblem.NOT_ALLOWED


@cache
def common_passwords() -> frozenset[str]:
    """The list shipped with the product, one lowercased password a line;
    `#` lines say where it came from."""
    text = files(__package__).joinpath(COMMON_LIST).read_text(encoding="utf-8")
    return frozenset(line.strip().lower() for line in text.splitlines() if line.strip() and not line.startswith("#"))


def password_problem(password: str, user_name: str) -> PasswordProblem | None:
    if len(password) < SHORTEST:
        return PasswordProblem.TOO_SHORT
    if len(password) > LONGEST:
        return PasswordProblem.TOO_LONG
    lowered = password.lower()
    if lowered in common_passwords():
        return PasswordProblem.TOO_COMMON
    if lowered == user_name.lower():
        return PasswordProblem.OWN_NAME
    return None
