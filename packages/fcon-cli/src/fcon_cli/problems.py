"""The error helper: every message a person reads, for every command. Each
says what is wrong and what to do, names a database by host, port and name,
never its password, and gives the development hints (docker compose) only
when the database is on this machine."""

from dataclasses import dataclass
from enum import StrEnum

from fcon_server import database
from fcon_server.database import ICU_COLLATION, DatabaseAddress, DatabaseCheck
from fcon_server.store.migrate import MigrationStatus

THIS_MACHINE = {"127.0.0.1", "localhost", "::1"}
SET_THE_ADDRESS = "Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather"
DEFAULT_PORT = 8080
RUN_UPGRADE = "Run: fcon db upgrade"
ENOUGH_MONTHS_AHEAD = 2  # fewer audit months after this one: a warning (design decision 4)
_NO_STATUS = MigrationStatus(applied=(), waiting=(), newer=(), changed=())


class Level(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"  # worth knowing, nothing to do


@dataclass(frozen=True)
class Problem:
    level: Level
    what: str  # what is wrong, one sentence
    todo: tuple[str, ...] = ()  # what to do, a line each

    def text(self) -> str:
        return "\n".join([f"{self.level}: {self.what}", *(f"  {line}" for line in self.todo)])


class ProblemError(Exception):
    """A problem only a person can fix: the command stops and says it."""

    def __init__(self, problem: Problem) -> None:
        super().__init__(problem.text())
        self.problem = problem


def _pick_port(port: int) -> str:
    return f"FCON_PORT={port} (or --port {port})"


# -- settings ------------------------------------------------------------


def database_url_missing() -> Problem:
    return Problem(
        Level.ERROR,
        "FCON_DATABASE_URL is not set.",
        (SET_THE_ADDRESS, "For development: copy .env.example to .env, then run: docker compose up -d"),
    )


def database_url_not_postgres(name: str = "FCON_DATABASE_URL") -> Problem:
    """Never repeats the address: it may hold a password."""
    return Problem(Level.ERROR, f"{name} is not a Postgres address.", (SET_THE_ADDRESS,))


def port_not_a_number(name: str, text: str) -> Problem:
    return Problem(
        Level.ERROR,
        f"{name} is not a port number: {text}.",
        (f"Use a number from 1 to 65535, for example: {_pick_port(DEFAULT_PORT)}",),
    )


def log_format_unknown(text: str) -> Problem:
    return Problem(
        Level.ERROR,
        f"FCON_LOG_FORMAT is not text or json: {text}.",
        ("Set it to text or json, or leave it unset: text on a terminal, json elsewhere.",),
    )


def usage(message: str, usage_text: str) -> Problem:
    """A mistake on the command line, as argparse words it."""
    return Problem(Level.ERROR, f"{message}.", (usage_text.strip(), "For every option: fcon --help"))


# -- listening -----------------------------------------------------------


def port_taken(host: str, port: int) -> Problem:
    return Problem(
        Level.ERROR,
        f"port {port} on {host} is already in use.",
        (f"Stop the program using it, or pick another port: {_pick_port(port + 1)}",),
    )


def port_not_allowed(host: str, port: int) -> Problem:
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
    return Problem(
        Level.ERROR,
        f"cannot listen on {host}: it is not an address of this machine.",
        ("Use 127.0.0.1 for this machine only, or 0.0.0.0 for every network: FCON_HOST=127.0.0.1 (or --host)",),
    )


def listening_beyond_machine(host: str, port: int) -> Problem:
    return Problem(
        Level.WARNING,
        f"listening on {host}:{port} can be reached from other machines.",
        ("Put it behind the host's HTTPS proxy, or keep it on this machine: FCON_HOST=127.0.0.1",),
    )


def bug() -> Problem:
    """Followed by the traceback."""
    return Problem(Level.ERROR, "this is a bug in Feather Connect; please report it with the lines below.")


# -- the database --------------------------------------------------------


def _where(address: DatabaseAddress) -> str:
    return f"{address.host}:{address.port}"


def _unusable(check: DatabaseCheck, setting: str) -> tuple[str, tuple[str, ...]]:
    """What is wrong with a database that is not usable, and what to do."""
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
    return f"{count} upgrade{'' if count == 1 else 's'}"


def _not_ready(check: DatabaseCheck) -> tuple[str, tuple[str, ...]]:
    """What is wrong with a database the server reaches but cannot use yet,
    and what to do; `_unusable` words the ones it cannot reach."""
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


def database_problem(check: DatabaseCheck) -> Problem:
    """The server's message for a database that is not usable (check.problem is set)."""
    if check.problem is database.Problem.CHANGED:
        return upgrade_changed((check.migrations or _NO_STATUS).changed[0].name)
    what, todo = _not_ready(check)
    return Problem(Level.WARNING, f"{what} Not ready.", todo)


def database_notes(check: DatabaseCheck) -> tuple[Problem, ...]:
    """What is worth saying, once, about a database that is usable: none of
    it stops the server being ready."""
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


def database_unusable(check: DatabaseCheck, setting: str) -> Problem:
    """A command's error for a database that is not usable, whose address it
    read from `setting`."""
    what, todo = _unusable(check, setting)
    return Problem(Level.ERROR, what, todo)


def upgrade_changed(name: str) -> Problem:
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
