"""Where `fcon server` gets its settings: FCON_* variables, .env in the
current directory for what they leave unset, and --host/--port for one run."""

from pathlib import Path

import pytest

from fcon_cli import problems
from fcon_cli.settings import Settings, SettingsError, load_settings

URL = "postgresql://feather:feather@127.0.0.1:5442/feather"


def test_it_listens_on_its_own_machine_at_8080_by_default(tmp_path: Path):
    settings = load_settings({"FCON_DATABASE_URL": URL}, tmp_path)

    assert settings == Settings(host="127.0.0.1", port=8080, database_url=URL)


def test_the_hosts_port_is_used_when_fcon_port_is_not_set(tmp_path: Path):
    settings = load_settings({"FCON_DATABASE_URL": URL, "PORT": "9000"}, tmp_path)

    assert settings.port == 9000


def test_fcon_port_wins_over_the_hosts_port(tmp_path: Path):
    settings = load_settings({"FCON_DATABASE_URL": URL, "PORT": "9000", "FCON_PORT": "9100"}, tmp_path)

    assert settings.port == 9100


def test_fcon_host_sets_where_it_listens(tmp_path: Path):
    settings = load_settings({"FCON_DATABASE_URL": URL, "FCON_HOST": "0.0.0.0"}, tmp_path)  # noqa: S104

    assert settings.host == "0.0.0.0"  # noqa: S104


def test_the_options_win_over_the_variables_for_one_run(tmp_path: Path):
    environ = {"FCON_DATABASE_URL": URL, "FCON_HOST": "0.0.0.0", "FCON_PORT": "9100"}  # noqa: S104

    settings = load_settings(environ, tmp_path, host="127.0.0.2", port=9200)

    assert (settings.host, settings.port) == ("127.0.0.2", 9200)


def test_env_file_fills_in_only_what_the_environment_leaves_unset(tmp_path: Path):
    (tmp_path / ".env").write_text(
        "# the worktree's settings\n\nFCON_PORT=18004\nFCON_DATABASE_URL=postgresql://x@h/from_file\n",
        encoding="utf-8",
    )

    settings = load_settings({"FCON_DATABASE_URL": URL}, tmp_path)

    assert (settings.port, settings.database_url) == (18004, URL)


def mistake(environ: dict[str, str], directory: Path, port: int | None = None) -> problems.Problem:
    with pytest.raises(SettingsError) as raised:
        load_settings(environ, directory, port=port)
    return raised.value.problem


def test_a_missing_database_address_is_a_settings_mistake(tmp_path: Path):
    assert mistake({}, tmp_path) == problems.database_url_missing()


@pytest.mark.parametrize(
    "url",
    [
        "mysql://feather@db.internal/feather",
        "feather",
        "postgresql://feather:secret@[db.internal/feather",
        "postgresql://feather:secret@db.internal:abc/feather",
    ],
)
def test_an_address_that_is_not_postgres_is_a_settings_mistake(tmp_path: Path, url: str):
    assert mistake({"FCON_DATABASE_URL": url}, tmp_path) == problems.database_url_not_postgres()


@pytest.mark.parametrize(
    "url", ["postgres://feather@db.internal/feather", "host=db.internal dbname=feather sslmode=require"]
)
def test_every_address_psycopg_reads_is_a_postgres_address(tmp_path: Path, url: str):
    assert load_settings({"FCON_DATABASE_URL": url}, tmp_path).database_url == url


def test_a_port_that_is_not_a_number_is_a_settings_mistake(tmp_path: Path):
    problem = mistake({"FCON_DATABASE_URL": URL, "FCON_PORT": "eighty"}, tmp_path)

    assert problem == problems.port_not_a_number("FCON_PORT", "eighty")


def test_the_hosts_port_is_named_when_it_is_not_a_number(tmp_path: Path):
    problem = mistake({"FCON_DATABASE_URL": URL, "PORT": "eighty"}, tmp_path)

    assert problem == problems.port_not_a_number("PORT", "eighty")


def test_a_port_beyond_65535_is_a_settings_mistake(tmp_path: Path):
    problem = mistake({"FCON_DATABASE_URL": URL, "FCON_PORT": "70000"}, tmp_path)

    assert problem == problems.port_not_a_number("FCON_PORT", "70000")


def test_a_port_option_of_0_is_a_settings_mistake(tmp_path: Path):
    assert mistake({"FCON_DATABASE_URL": URL}, tmp_path, port=0) == problems.port_not_a_number("--port", "0")


def test_the_log_format_is_read_with_the_settings(tmp_path: Path):
    settings = load_settings({"FCON_DATABASE_URL": URL, "FCON_LOG_FORMAT": "json"}, tmp_path)

    assert settings.log_format == "json"


def test_an_unknown_log_format_is_a_settings_mistake(tmp_path: Path):
    problem = mistake({"FCON_DATABASE_URL": URL, "FCON_LOG_FORMAT": "yaml"}, tmp_path)

    assert problem == problems.log_format_unknown("yaml")
