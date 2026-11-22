"""Where the commands get their settings: FCON_* variables, .env in the
current directory for what they leave unset, and --host/--port for one run
of `fcon server`."""

from pathlib import Path

import pytest

from fcon_cli import problems
from fcon_cli.settings import DatabaseSettings, Settings, SettingsError, load_database_settings, load_settings

URL = "postgresql://feather:feather@127.0.0.1:5442/feather"
KEY = "k" * 32
BASE = {"FCON_DATABASE_URL": URL, "FCON_SECRET_KEY": KEY}


def test_it_listens_on_its_own_machine_at_8080_by_default(tmp_path: Path):
    settings = load_settings(BASE, tmp_path)

    assert settings == Settings(host="127.0.0.1", port=8080, database_url=URL, secret_key=KEY)


def test_the_hosts_port_is_used_when_fcon_port_is_not_set(tmp_path: Path):
    settings = load_settings({**BASE, "PORT": "9000"}, tmp_path)

    assert settings.port == 9000


def test_fcon_port_wins_over_the_hosts_port(tmp_path: Path):
    settings = load_settings({**BASE, "PORT": "9000", "FCON_PORT": "9100"}, tmp_path)

    assert settings.port == 9100


def test_fcon_host_sets_where_it_listens(tmp_path: Path):
    settings = load_settings({**BASE, "FCON_HOST": "0.0.0.0"}, tmp_path)  # noqa: S104

    assert settings.host == "0.0.0.0"  # noqa: S104


def test_the_options_win_over_the_variables_for_one_run(tmp_path: Path):
    environ = {**BASE, "FCON_HOST": "0.0.0.0", "FCON_PORT": "9100"}  # noqa: S104

    settings = load_settings(environ, tmp_path, host="127.0.0.2", port=9200)

    assert (settings.host, settings.port) == ("127.0.0.2", 9200)


def test_env_file_fills_in_only_what_the_environment_leaves_unset(tmp_path: Path):
    (tmp_path / ".env").write_text(
        "# the worktree's settings\n\nFCON_PORT=18004\nFCON_DATABASE_URL=postgresql://x@h/from_file\n",
        encoding="utf-8",
    )

    settings = load_settings(BASE, tmp_path)

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
    assert load_settings({**BASE, "FCON_DATABASE_URL": url}, tmp_path).database_url == url


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
    settings = load_settings({**BASE, "FCON_LOG_FORMAT": "json"}, tmp_path)

    assert settings.log_format == "json"


def test_an_unknown_log_format_is_a_settings_mistake(tmp_path: Path):
    problem = mistake({"FCON_DATABASE_URL": URL, "FCON_LOG_FORMAT": "yaml"}, tmp_path)

    assert problem == problems.log_format_unknown("yaml")


def test_the_pool_has_5_connections_when_its_size_is_unset(tmp_path: Path):
    assert load_settings(BASE, tmp_path).pool_size == 5


def test_the_pool_size_is_read_with_the_settings(tmp_path: Path):
    settings = load_settings({**BASE, "FCON_DATABASE_POOL_SIZE": "12"}, tmp_path)

    assert settings.pool_size == 12


@pytest.mark.parametrize("text", ["0", "five", "-3"], ids=["zero", "a-word", "negative"])
def test_a_pool_size_that_is_not_a_whole_number_from_1_is_a_settings_mistake(tmp_path: Path, text: str):
    problem = mistake({"FCON_DATABASE_URL": URL, "FCON_DATABASE_POOL_SIZE": text}, tmp_path)

    assert problem == problems.pool_size_not_a_number(text)


@pytest.mark.parametrize(("text", "prepare"), [("", True), ("on", True), ("off", False)], ids=["unset", "on", "off"])
def test_prepared_statements_are_turned_off_only_by_off(tmp_path: Path, text: str, prepare: bool):
    environ = BASE | ({"FCON_DATABASE_PREPARE": text} if text else {})

    assert load_settings(environ, tmp_path).prepare is prepare


def test_a_prepare_setting_other_than_on_or_off_is_a_settings_mistake(tmp_path: Path):
    problem = mistake({"FCON_DATABASE_URL": URL, "FCON_DATABASE_PREPARE": "no"}, tmp_path)

    assert problem == problems.prepare_unknown("no")


OWNER_URL = "postgresql://owner:secret@127.0.0.1:5442/feather"


def test_the_database_commands_use_the_app_address_for_upgrades_when_no_owner_address_is_set(tmp_path: Path):
    settings = load_database_settings({"FCON_DATABASE_URL": URL}, tmp_path)

    assert settings == DatabaseSettings(database_url=URL, migration_database_url=URL)


def test_the_owner_address_is_used_for_upgrades_when_it_is_set(tmp_path: Path):
    settings = load_database_settings({"FCON_DATABASE_URL": URL, "FCON_MIGRATION_DATABASE_URL": OWNER_URL}, tmp_path)

    assert settings == DatabaseSettings(database_url=URL, migration_database_url=OWNER_URL)


def test_the_database_commands_read_env_file_for_what_the_environment_leaves_unset(tmp_path: Path):
    (tmp_path / ".env").write_text(
        f"FCON_DATABASE_URL={URL}\nFCON_MIGRATION_DATABASE_URL={OWNER_URL}\n", encoding="utf-8"
    )

    assert load_database_settings({}, tmp_path).migration_database_url == OWNER_URL


def test_the_database_commands_need_the_app_address(tmp_path: Path):
    with pytest.raises(SettingsError) as raised:
        load_database_settings({"FCON_MIGRATION_DATABASE_URL": OWNER_URL}, tmp_path)

    assert raised.value.problem == problems.database_url_missing()


def test_an_owner_address_that_is_not_postgres_is_a_settings_mistake(tmp_path: Path):
    with pytest.raises(SettingsError) as raised:
        load_database_settings({"FCON_DATABASE_URL": URL, "FCON_MIGRATION_DATABASE_URL": "feather"}, tmp_path)

    assert raised.value.problem == problems.database_url_not_postgres("FCON_MIGRATION_DATABASE_URL")


# -- the secret key and the environment's name ------------------------------


def test_the_secret_key_is_read_with_the_settings(tmp_path: Path):
    assert load_settings(BASE, tmp_path).secret_key == KEY


def test_a_missing_secret_key_is_a_settings_mistake(tmp_path: Path):
    assert mistake({"FCON_DATABASE_URL": URL}, tmp_path) == problems.secret_key_missing()


def test_a_secret_key_under_32_characters_is_a_settings_mistake(tmp_path: Path):
    assert mistake({**BASE, "FCON_SECRET_KEY": "k" * 31}, tmp_path) == problems.secret_key_too_short("FCON_SECRET_KEY")


def test_there_is_no_previous_secret_key_unless_one_is_set(tmp_path: Path):
    assert load_settings(BASE, tmp_path).previous_secret_key is None


def test_the_previous_secret_key_is_read_with_the_settings(tmp_path: Path):
    settings = load_settings({**BASE, "FCON_SECRET_KEY_PREVIOUS": "p" * 32}, tmp_path)

    assert settings.previous_secret_key == "p" * 32


def test_a_previous_secret_key_under_32_characters_is_a_settings_mistake(tmp_path: Path):
    assert mistake({**BASE, "FCON_SECRET_KEY_PREVIOUS": "p" * 31}, tmp_path) == problems.secret_key_too_short(
        "FCON_SECRET_KEY_PREVIOUS"
    )


def test_the_environment_is_development_unless_named(tmp_path: Path):
    assert load_settings(BASE, tmp_path).environment == "development"


def test_the_environments_name_is_read_with_the_settings(tmp_path: Path):
    assert load_settings({**BASE, "FCON_ENVIRONMENT": " staging "}, tmp_path).environment == "staging"


# -- the first administrator --------------------------------------------------


def test_no_first_administrator_is_named_unless_set(tmp_path: Path):
    assert load_settings(BASE, tmp_path).first_admin is None


def test_the_first_administrator_is_read_as_a_user_name_is_stored(tmp_path: Path):
    assert load_settings({**BASE, "FCON_FIRST_ADMIN": " Ann "}, tmp_path).first_admin == "ann"


def test_a_first_administrator_whose_name_breaks_the_rules_is_a_settings_mistake(tmp_path: Path):
    assert mistake({**BASE, "FCON_FIRST_ADMIN": "ann smith"}, tmp_path) == problems.first_admin_not_allowed("ann smith")
