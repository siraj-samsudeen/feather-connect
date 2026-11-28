"""The error helper: every message a person reads, for every command.

Each says what is wrong and what to do, names a database by host, port and name, never its password, and gives the
development hints (docker compose) only when the database is on this machine.
"""

from dataclasses import dataclass
from enum import StrEnum

from fcon_server import database
from fcon_server.catalog.known_settings import Kind, settings_of
from fcon_server.database import ICU_COLLATION, DatabaseAddress, DatabaseCheck
from fcon_server.store.migrate import MigrationStatus
from fcon_server.users import rules
from fcon_server.users.rules import PasswordProblem

THIS_MACHINE = {"127.0.0.1", "localhost", "::1"}
SET_THE_ADDRESS = "Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather"
DEFAULT_PORT = 8080
RUN_UPGRADE = "Run: fcon db upgrade"
ENOUGH_MONTHS_AHEAD = 3  # fewer audit months after this one: a warning (design decision 4)
_NO_STATUS = MigrationStatus(applied=(), waiting=(), newer=(), changed=())


class Level(StrEnum):
    """How serious a problem is; a problem's text starts with it."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"  # worth knowing, nothing to do


@dataclass(frozen=True)
class Problem:
    """A message for a person: what is wrong, at a level, and what to do about it."""

    level: Level
    what: str  # what is wrong, one sentence
    todo: tuple[str, ...] = ()  # what to do, a line each

    def text(self) -> str:
        """The message as printed: "level: what", then each thing to do on an indented line of its own."""
        return "\n".join([f"{self.level}: {self.what}", *(f"  {line}" for line in self.todo)])


class ProblemError(Exception):
    """A problem only a person can fix: the command stops and says it."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.text())
        self.problem = problem


def _pick_port(port: int) -> str:
    """How to choose `port`: the setting, or the option for one run."""
    return f"FCON_PORT={port} (or --port {port})"


# -- settings ------------------------------------------------------------


def database_url_missing() -> Problem:
    """The problem when FCON_DATABASE_URL is not set."""
    return Problem(
        Level.ERROR,
        "FCON_DATABASE_URL is not set.",
        (SET_THE_ADDRESS, "For development: copy .env.example to .env, then run: docker compose up -d"),
    )


def database_url_not_postgres(name: str = "FCON_DATABASE_URL") -> Problem:
    """The problem when the setting `name` is not a Postgres address.

    Never repeats the address: it may hold a password.
    """
    return Problem(Level.ERROR, f"{name} is not a Postgres address.", (SET_THE_ADDRESS,))


def port_not_a_number(name: str, text: str) -> Problem:
    """The problem when the setting or option `name` holds `text`, which is not a port from 1 to 65535."""
    return Problem(
        Level.ERROR,
        f"{name} is not a port number: {text}.",
        (f"Use a number from 1 to 65535, for example: {_pick_port(DEFAULT_PORT)}",),
    )


def log_format_unknown(text: str) -> Problem:
    """The problem when FCON_LOG_FORMAT is neither text nor json."""
    return Problem(
        Level.ERROR,
        f"FCON_LOG_FORMAT is not text or json: {text}.",
        ("Set it to text or json, or leave it unset: text on a terminal, json elsewhere.",),
    )


def pool_size_not_a_number(text: str) -> Problem:
    """The problem when FCON_DATABASE_POOL_SIZE is not a whole number from 1 up."""
    return Problem(
        Level.ERROR,
        f"FCON_DATABASE_POOL_SIZE is not a number of connections: {text}.",
        ("Use a whole number from 1 up, or leave it unset for 5.",),
    )


def prepare_unknown(text: str) -> Problem:
    """The problem when FCON_DATABASE_PREPARE is neither on nor off."""
    return Problem(
        Level.ERROR,
        f"FCON_DATABASE_PREPARE is not on or off: {text}.",
        ("Set it to off when a connection pooler sits in front of Postgres; leave it unset otherwise.",),
    )


MAKE_A_KEY = 'python -c "import secrets; print(secrets.token_urlsafe(32))"'


def secret_key_missing() -> Problem:
    """The problem when FCON_SECRET_KEY is not set, with a command that makes one."""
    return Problem(
        Level.ERROR,
        "FCON_SECRET_KEY is not set.",
        ("Every install needs one of at least 32 random characters. Make one with:", MAKE_A_KEY),
    )


def secret_key_too_short(name: str) -> Problem:
    """The problem when the key in the setting `name` is shorter than 32 characters.

    Never repeats the key: it is a secret.
    """
    return Problem(Level.ERROR, f"{name} is shorter than 32 characters.", ("Make a longer one with:", MAKE_A_KEY))


def first_admin_not_allowed(name: str) -> Problem:
    """The problem when FCON_FIRST_ADMIN is not an allowed user name."""
    return Problem(
        Level.ERROR,
        f"FCON_FIRST_ADMIN is not an allowed user name: {name!r}.",
        ("Use 1 to 64 lowercase letters, digits and . _ - @ +; an email address works.",),
    )


def first_admin_made(name: str, password: str) -> Problem:
    """The warning that gives the first administrator's one-time password.

    The one place a one-time password is written: the log, once (design point 1).
    """
    return Problem(
        Level.WARNING,
        f'no administrator yet; made "{name}" with a one-time password: {password}',
        ("Sign in at /sign-in and choose your own password. Remove FCON_FIRST_ADMIN afterwards.",),
    )


def usage(message: str, usage_text: str) -> Problem:
    """A mistake on the command line, as argparse words it."""
    return Problem(Level.ERROR, f"{message}.", (usage_text.strip(), "For every option: fcon --help"))


# -- listening -----------------------------------------------------------


def port_taken(host: str, port: int) -> Problem:
    """The problem when the port is already in use, suggesting the next one."""
    return Problem(
        Level.ERROR,
        f"port {port} on {host} is already in use.",
        (f"Stop the program using it, or pick another port: {_pick_port(port + 1)}",),
    )


def port_not_allowed(host: str, port: int) -> Problem:
    """The problem when this machine does not allow listening on the port, suggesting another."""
    other = DEFAULT_PORT if port < 1024 else port + 1
    return Problem(
        Level.ERROR,
        f"this machine does not allow listening on port {port} on {host}.",
        (
            "Ports below 1024 need extra rights, and Windows reserves some ranges for itself.",
            f"Pick another port: {_pick_port(other)}",
        ),
    )


def host_not_here(host: str) -> Problem:
    """The problem when the server cannot listen on `host`: it is not an address of this machine."""
    return Problem(
        Level.ERROR,
        f"cannot listen on {host}: it is not an address of this machine.",
        ("Use 127.0.0.1 for this machine only, or 0.0.0.0 for every network: FCON_HOST=127.0.0.1 (or --host)",),
    )


def listening_beyond_machine(host: str, port: int) -> Problem:
    """The warning that the server listens where other machines can reach it."""
    return Problem(
        Level.WARNING,
        f"listening on {host}:{port} can be reached from other machines.",
        ("Put it behind the host's HTTPS proxy, or keep it on this machine: FCON_HOST=127.0.0.1",),
    )


def trusted_proxies_not_addresses(item: str) -> Problem:
    """The problem when an item of FCON_TRUSTED_PROXIES is not an address or a range."""
    return Problem(
        Level.ERROR,
        f"FCON_TRUSTED_PROXIES is not a list of addresses or ranges: {item!r}.",
        (
            "Name the proxy's addresses or ranges, comma-separated, such as 172.16.0.0/12,10.0.0.5;",
            "or * where only the proxy can reach the server (docs/deploy.md).",
        ),
    )


def untrusted_forwarding() -> Problem:
    """The warning that requests carry X-Forwarded-For but no proxy is trusted.

    Logged once per process (design point 8).
    """
    return Problem(Level.WARNING, "requests carry X-Forwarded-For, but no proxy is trusted; set FCON_TRUSTED_PROXIES.")


def bug() -> Problem:
    """The error for an unexpected failure, a bug in Feather Connect; the traceback follows it."""
    return Problem(Level.ERROR, "this is a bug in Feather Connect; please report it with the lines below.")


# -- the database --------------------------------------------------------


def _where(address: DatabaseAddress) -> str:
    """The database's host and port, as host:port."""
    return f"{address.host}:{address.port}"


def _unusable(check: DatabaseCheck, setting: str) -> tuple[str, tuple[str, ...]]:
    """What is wrong with a database that is not usable, and what to do.

    `setting` names the setting that holds its address.
    """
    address = check.address
    local = address.host in THIS_MACHINE
    match check.problem:
        case database.Problem.DATABASE_MISSING:
            todo = (
                f"Create it: docker compose exec db createdb -U {address.user} {address.dbname}"
                if local
                else f"Create it on that server, or correct its name in {setting}."
            )
            return f"the database {address.dbname} does not exist on {_where(address)}.", (todo,)
        case database.Problem.LOGIN_REFUSED:
            what = f"the database at {_where(address)} refused the login of user {address.user}."
            return what, (f"Check the user and password in {setting}.",)
        case database.Problem.TOO_OLD:
            return f"Postgres {check.version} found at {_where(address)}; Feather Connect needs 18 or later.", ()
        case _:
            reason = f" ({check.reason})" if check.reason else ""
            todo = (
                "Start it: docker compose up -d"
                if local
                else f"Check the host and port in {setting}, and that the database server is running."
            )
            return f"cannot reach the database at {_where(address)}{reason}.", (todo,)


def _upgrades(count: int) -> str:
    """The number of upgrades in words: "1 upgrade", "3 upgrades"."""
    return f"{count} upgrade{'' if count == 1 else 's'}"


def _not_ready(check: DatabaseCheck) -> tuple[str, tuple[str, ...]]:
    """What is wrong with a database the server reaches but cannot use yet, and what to do.

    `_unusable` words the ones it cannot reach.
    """
    status = check.migrations or _NO_STATUS
    match check.problem:
        case database.Problem.NOT_UTF8:
            what = (
                f"the database {check.address.dbname} uses the encoding {check.encoding};"
                f" Feather Connect needs {database.ENCODING}."
            )
            todo = (
                "Make a new database in UTF-8 (createdb -E UTF8 -T template0 <name>),"
                " point FCON_DATABASE_URL at it, then run: fcon db upgrade"
            )
            return what, (todo,)
        case database.Problem.BEHIND:
            return f"the database is {_upgrades(len(status.waiting))} behind this version.", (RUN_UPGRADE,)
        case database.Problem.AUDIT_MONTH_MISSING:
            return "the audit log has no partition for this month, so no change can be saved.", (RUN_UPGRADE,)
        case _:
            return _unusable(check, "FCON_DATABASE_URL")


def _database_problem(check: DatabaseCheck, level: Level, after: str) -> Problem:
    """The problem for a database that is not usable, at `level`, with `after` added to what is wrong.

    An upgrade that has changed since it ran has its own error, whatever the level.
    """
    if check.problem is database.Problem.CHANGED:
        return upgrade_changed((check.migrations or _NO_STATUS).changed[0].name)
    what, todo = _not_ready(check)
    return Problem(level, f"{what}{after}", todo)


def database_problem(check: DatabaseCheck) -> Problem:
    """The server's message for a database that is not usable (check.problem is set)."""
    return _database_problem(check, Level.WARNING, " Not ready.")


def database_notes(check: DatabaseCheck) -> tuple[Problem, ...]:
    """What is worth saying, once, about a database that is usable; nothing for one that is not.

    None of it stops the server being ready.
    """
    if check.problem is not None:
        return ()
    notes: list[Problem] = []
    if newer := (check.migrations or _NO_STATUS).newer:
        what = (
            f"the database has {_upgrades(len(newer))} newer than this version; expand-only upgrades keep it working."
        )
        notes.append(Problem(Level.INFO, what))
    if not check.icu:
        notes.append(
            Problem(
                Level.WARNING, f"the database has no ICU collation ({ICU_COLLATION}), so lists sort by character code."
            )
        )
    if check.months_ahead < ENOUGH_MONTHS_AHEAD:
        months = f"{check.months_ahead} month{'' if check.months_ahead == 1 else 's'}"
        notes.append(
            Problem(Level.WARNING, f"the audit log has partitions for only {months} after this one.", (RUN_UPGRADE,))
        )
    return tuple(notes)


def database_not_ready_for_command(check: DatabaseCheck) -> Problem:
    """A command's error for a database it cannot use (check.problem is set)."""
    return _database_problem(check, Level.ERROR, "")


def database_unusable(check: DatabaseCheck, setting: str) -> Problem:
    """A command's error for a database that is not usable, whose address it read from `setting`."""
    what, todo = _unusable(check, setting)
    return Problem(Level.ERROR, what, todo)


def upgrade_changed(name: str) -> Problem:
    """The problem when the upgrade `name` has changed since it ran."""
    return Problem(
        Level.ERROR, f"upgrade {name} has changed since it ran.", ("Restore it; never edit a migration that ran.",)
    )


def waiting_for_upgrade() -> str:
    """Not a problem: another upgrade holds the database for a moment."""
    return "waiting for another upgrade of the database to finish..."


def database_usable(check: DatabaseCheck, again: bool = False) -> str:
    """Not a problem: the line that says the database is ready."""
    address = check.address
    return f"the database {address.dbname} at {_where(address)} is usable{' again' if again else ''}. Ready."


# -- users ---------------------------------------------------------------

_PASSWORD_TODO = {
    PasswordProblem.TOO_SHORT: f"Use at least {rules.SHORTEST} characters.",
    PasswordProblem.TOO_LONG: f"Use at most {rules.LONGEST} characters.",
    PasswordProblem.TOO_COMMON: "Choose one that is not among the most common passwords.",
    PasswordProblem.OWN_NAME: "Choose one that is not the user name.",
}


def user_name_not_allowed(name: str) -> Problem:
    """The problem when `name` is not an allowed user name."""
    return Problem(
        Level.ERROR,
        f"the user name {name!r} is not allowed.",
        ("Use 1 to 64 lowercase letters, digits and . _ - @ +; an email address works.",),
    )


def user_name_taken(name: str) -> Problem:
    """The problem when another user has the name already."""
    return Problem(Level.ERROR, f"the user name {name} is taken.", ("Pick another name.",))


def weak_password(problem: PasswordProblem) -> Problem:
    """The problem when the password breaks a rule, with how to meet it."""
    return Problem(Level.ERROR, f"the password is {problem}.", (_PASSWORD_TODO[problem],))


def no_password() -> Problem:
    """The problem when no password was given."""
    return Problem(Level.ERROR, "no password was given.", ("Type it when asked, or give it as one line on stdin.",))


def passwords_differ() -> Problem:
    """The problem when the password typed again differs from the first."""
    return Problem(Level.ERROR, "the two passwords typed differ.", ("Type the same password twice.",))


def no_such_user(name: str) -> Problem:
    """The problem when no user has the name."""
    return Problem(Level.ERROR, f"no user is named {name}.", ("See who there is: fcon users list",))


def only_administrator(reason: str) -> Problem:
    """The problem when a change would leave no administrator; `reason` says who the only one is."""
    return Problem(
        Level.ERROR, reason, ("Make another user an administrator: fcon users set-role <name> administrator",)
    )


# -- the catalog and settings --------------------------------------------


def not_definitions_file(file: str, what: str, expected: str) -> Problem:
    """The problem when `file` is not a package version's definitions: `what` is wrong, `expected` is wanted."""
    return Problem(Level.ERROR, f"{file} is not a definitions file: {what}.", (expected,))


def definitions_file_unreadable(file: str) -> Problem:
    """The problem when `file` cannot be read at all."""
    return not_definitions_file(file, "it cannot be read", "Give the path of a definitions file, JSON in UTF-8.")


def recorded_with_other_definitions(package: str, version: str) -> Problem:
    """The problem when a package version is recorded already with other definitions."""
    return Problem(
        Level.ERROR,
        f"{package} {version} is recorded already, with other definitions.",
        ("A recorded version never changes: give the changed code a new version.",),
    )


def _settings_of(kind: Kind) -> str:
    """Every setting of `kind`, in the list's order, as a line of what to do."""
    return f"A {kind}'s settings: {', '.join(setting.name for setting in settings_of(kind))}"


def decided_by_code(name: str, kind: Kind, setting: str) -> Problem:
    """The problem when `setting` of the entry `name` is the code's to decide."""
    return Problem(
        Level.ERROR, f"the {setting} of {name} is decided by the code, not by a setting.", (_settings_of(kind),)
    )


def no_such_setting(kind: Kind, setting: str) -> Problem:
    """The problem when a `kind` has no setting named `setting`."""
    return Problem(Level.ERROR, f"a {kind} has no setting named {setting}.", (_settings_of(kind),))


def bad_setting_value(value: str, setting: str, expected: str) -> Problem:
    """The problem when `value` is not a value of `setting`; `expected` says what is."""
    article = "an" if setting[0] in "aeiou" else "a"
    return Problem(Level.ERROR, f'"{value}" is not {article} {setting}.', (expected,))


def kind_changed(reason: str) -> Problem:
    """The problem when a package version declares a known name as another kind; `reason` says which."""
    return Problem(Level.ERROR, f"{reason}.", ("A name keeps its kind: give the new one a name of its own.",))


def rename_across_kinds(reason: str) -> Problem:
    """The problem when a package version renames an entry of one kind to a name of another."""
    return Problem(
        Level.ERROR,
        f"{reason}.",
        ("A rename keeps the kind: give the new one a name of its own, without renamed_from.",),
    )


def flagged_value(name: str, setting: str) -> Problem:
    """The warning for an operator's value of `name`, which the code no longer has."""
    return Problem(
        Level.WARNING,
        f"the operator's {setting} of {name} is for a name the code no longer has.",
        (f"Clear it with: fcon settings clear {name} {setting}",),
    )
