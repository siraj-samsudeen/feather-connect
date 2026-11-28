"""How a command reaches the server's services: the store on the app's address, and the command line as a caller.

The command line acts as `system:cli` with every right, in the request's tenant: whoever can run it can reach the
database anyway.
"""

from fcon_cli import problems
from fcon_cli.problems import ProblemError
from fcon_cli.settings import DatabaseSettings
from fcon_server.database import diagnose_database
from fcon_server.store.clock import SystemClock
from fcon_server.store.context import Context
from fcon_server.store.ids import new_id
from fcon_server.store.pool import OneConnectionEach
from fcon_server.store.transaction import Store
from fcon_server.users.rights import Caller, Role
from fcon_server.users.tenant import request_tenant

ACTOR = "system:cli"
APPLICATION_NAME = "fcon-cli"


def cli_caller() -> Caller:
    """The command line as a caller with every right, as `system:cli` in the request's tenant."""
    context = Context(tenant_id=request_tenant(), actor=ACTOR, request_id=f"cli-{new_id()}")
    return Caller(context, Role.ADMINISTRATOR)


def open_store(settings: DatabaseSettings) -> Store:
    """The store on the app's address; raises ProblemError when the database is not ready for a command."""
    check = diagnose_database(settings.database_url)
    if check.problem is not None:
        raise ProblemError(problems.database_not_ready_for_command(check))
    return Store(OneConnectionEach(settings.database_url, APPLICATION_NAME), SystemClock(), new_id)
