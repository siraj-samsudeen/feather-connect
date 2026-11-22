"""`fcon users add` (design point 1, § How it is built): the password asked on
a terminal, else one line of stdin; every refusal through the error helper,
exit code 2. It acts as `system:cli` in the tenant `default`."""

import io
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import psycopg
import pytest
from psycopg.rows import dict_row

from fcon_cli.main import main
from fcon_cli.problems import ProblemError
from fcon_cli.users import read_password
from fcon_server.store.clock import SystemClock
from fcon_server.store.migrate import upgrade

PASSWORD = "blue-harbour-lamp"


class Terminal(io.StringIO):
    def isatty(self) -> bool:
        return True


@pytest.fixture
def database(empty_database_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[str]:
    """An upgraded database of the test's own, named by FCON_DATABASE_URL; no .env."""
    upgrade(empty_database_url, SystemClock())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", empty_database_url)
    yield empty_database_url


def users_add(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], *argv: str, typed: str = PASSWORD + "\n"
) -> tuple[int, str, str]:
    monkeypatch.setattr("sys.stdin", io.StringIO(typed))
    code = main(["users", "add", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def users(database_url: str) -> list[dict[str, Any]]:
    with psycopg.connect(database_url) as connection:
        return (
            connection.cursor(row_factory=dict_row)
            .execute("SELECT * FROM fcon.user ORDER BY created_at, name")
            .fetchall()
        )


@pytest.mark.database
def test_the_first_user_added_is_an_administrator(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    assert [(row["name"], row["role"]) for row in users(database)] == [("ann", "administrator")]


@pytest.mark.database
def test_the_user_is_added_to_the_default_tenant(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    assert users(database)[0]["tenant_id"] == "default"


@pytest.mark.database
def test_the_command_acts_as_the_command_line(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    assert users(database)[0]["created_by"] == "system:cli"


@pytest.mark.database
def test_adding_the_first_user_says_who_was_added(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    assert users_add(monkeypatch, capsys, "ann", "--admin") == (0, "added the user ann, an administrator.\n", "")


@pytest.mark.database
def test_a_later_user_gets_the_role_given(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    users_add(monkeypatch, capsys, "ben@example.com", "--role", "operator", typed="given-once-0001\n")

    assert users(database)[1]["role"] == "operator"


@pytest.mark.database
def test_a_later_user_is_told_to_choose_a_password_at_sign_in(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    _, out, _ = users_add(monkeypatch, capsys, "ben@example.com", "--role", "operator", typed="given-once-0001\n")

    assert out == (
        "added the user ben@example.com, an operator.\n"
        "Their password works for one sign-in; then they choose their own.\n"
    )


@pytest.mark.database
def test_admin_makes_a_later_user_an_administrator(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    users_add(monkeypatch, capsys, "cat", "--admin", typed="cat-password-01\n")

    assert users(database)[1]["role"] == "administrator"


@pytest.mark.database
def test_a_later_user_without_a_role_is_a_viewer(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    users_add(monkeypatch, capsys, "ann")

    users_add(monkeypatch, capsys, "cat", typed="cat-password-01\n")

    assert users(database)[1]["role"] == "viewer"


@pytest.mark.database
def test_a_display_name_is_kept(database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    users_add(monkeypatch, capsys, "ann", "--display-name", "Ann Lee")

    assert users(database)[0]["display_name"] == "Ann Lee"


@pytest.mark.database
def test_a_name_taken_is_a_problem(database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    users_add(monkeypatch, capsys, "ann")

    assert users_add(monkeypatch, capsys, "ann", typed="another-password\n") == (
        2,
        "",
        "error: the user name ann is taken.\n  Pick another name.\n",
    )


@pytest.mark.database
def test_a_name_outside_the_rules_is_a_problem(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    assert users_add(monkeypatch, capsys, "ann smith") == (
        2,
        "",
        (
            "error: the user name 'ann smith' is not allowed.\n"
            "  Use 1 to 64 lowercase letters, digits and . _ - @ +; an email address works.\n"
        ),
    )


@pytest.mark.database
@pytest.mark.parametrize(
    ("password", "what", "todo"),
    [
        ("short-one", "too short", "Use at least 12 characters."),
        ("x" * 129, "too long", "Use at most 128 characters."),
        ("password123456", "too common", "Choose one that is not among the most common passwords."),
        ("ann-the-admin", None, None),
    ],
    ids=["too-short", "too-long", "too-common", "fine"],
)
def test_a_weak_password_is_a_problem_saying_which_rule_failed(
    database: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    password: str,
    what: str | None,
    todo: str | None,
):
    expected = (0, "") if what is None else (2, f"error: the password is {what}.\n  {todo}\n")

    code, _, err = users_add(monkeypatch, capsys, "ann", typed=password + "\n")

    assert (code, err) == expected


@pytest.mark.database
def test_a_password_that_is_the_users_name_is_a_problem(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    assert users_add(monkeypatch, capsys, "ann@example.com", typed="ann@example.com\n") == (
        2,
        "",
        "error: the password is the user's own name.\n  Choose one that is not the user name.\n",
    )


@pytest.mark.database
def test_no_password_on_stdin_is_a_problem(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    assert users_add(monkeypatch, capsys, "ann", typed="") == (
        2,
        "",
        "error: no password was given.\n  Type it when asked, or give it as one line on stdin.\n",
    )


@pytest.mark.database
def test_the_password_is_never_printed(
    database: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    _, out, err = users_add(monkeypatch, capsys, "ann")

    assert PASSWORD not in out + err


def test_admin_and_a_role_together_are_a_usage_problem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
):
    code, _, err = users_add(monkeypatch, capsys, "ann", "--admin", "--role", "viewer")

    assert (code, err.splitlines()[0]) == (2, "error: argument --role: not allowed with argument --admin.")


@pytest.mark.database
def test_a_database_not_upgraded_is_a_problem(
    empty_database_url: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", empty_database_url)

    code, _, err = users_add(monkeypatch, capsys, "ann")

    assert (code, err.splitlines()[1]) == (2, "  Run: fcon db upgrade")


def test_a_database_out_of_reach_is_a_problem(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], tmp_path: Path, free_port: int
):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("FCON_DATABASE_URL", f"postgresql://feather:feather@127.0.0.1:{free_port}/feather")

    code, _, err = users_add(monkeypatch, capsys, "ann")

    assert (code, err.splitlines()[0]) == (
        2,
        f"error: cannot reach the database at 127.0.0.1:{free_port} (connection refused).",
    )


# -- the password, on a terminal or not ------------------------------------


def asking(*answers: str) -> tuple[Callable[[str], str], list[str]]:
    prompts: list[str] = []
    replies = iter(answers)

    def ask(prompt: str) -> str:
        prompts.append(prompt)
        return next(replies)

    return ask, prompts


def test_off_a_terminal_the_password_is_one_line_of_stdin():
    ask, _ = asking()

    assert read_password(io.StringIO("blue-harbour-lamp\r\nmore\n"), ask) == PASSWORD


def test_on_a_terminal_the_password_is_asked_twice():
    ask, prompts = asking(PASSWORD, PASSWORD)

    read_password(Terminal(), ask)

    assert prompts == ["Password: ", "The same again: "]


def test_on_a_terminal_the_password_typed_is_given():
    ask, _ = asking(PASSWORD, PASSWORD)

    assert read_password(Terminal(), ask) == PASSWORD


def test_two_passwords_that_differ_are_a_problem():
    ask, _ = asking(PASSWORD, "blue-harbour-lam")

    with pytest.raises(ProblemError, match="the two passwords typed differ"):
        read_password(Terminal(), ask)
