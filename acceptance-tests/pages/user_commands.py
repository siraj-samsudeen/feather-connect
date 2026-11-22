"""The operator's terminal for users: `fcon users ...` typed at a prompt, the
password typed into it (it reads one line from stdin when that is not a
terminal), and what it printed. The commands, their flags and the texts the
steps rely on live here; the steps only ask questions.

Each command runs against the database of the product the scenario talks to,
with only that address as its setting (support/stack.py, start_fcon).
"""

from pages.database_commands import Result
from support import run_database, stack

USERS = "users"
ADD = "add"
ADMIN_FLAG = "--admin"
ROLE_FLAG = "--role"
DATABASE_SETTING = "FCON_DATABASE_URL"


class UserCommands:
    def __init__(self, world):
        self.world = world
        self.result = None
        self.results = []  # every command of the scenario, in order

    def _settings(self):
        return {DATABASE_SETTING: self.world.product_database_url()}

    def _run(self, arguments, typed=None):
        process = stack.start_fcon([USERS, *arguments], self._settings(), stdin_text=typed)
        code, out, err, timed_out = stack.finish_fcon(process)
        # What was typed is a password: the record of the command never shows it.
        result = Result(" ".join([USERS, *arguments]), code, out, err, timed_out)
        self.world.screen.command("fcon " + result.command, out + err, code)
        self.results.append(result)
        self.result = result
        return result

    # -- the commands ----------------------------------------------------

    def add(self, name, password, administrator=False, role=None):
        """`fcon users add <name> [--admin] [--role R]`, the password typed on stdin."""
        arguments = [ADD, name]
        if administrator:
            arguments.append(ADMIN_FLAG)
        if role is not None:
            arguments += [ROLE_FLAG, role]
        return self._run(arguments, typed=password + "\n")

    def add_administrator(self, name, password):
        """As setup: an administrator with that password, or an AssertionError
        saying what the command answered."""
        result = self.add(name, password, administrator=True)
        if not result.ended_well():
            raise AssertionError("could not add the administrator %r; %r" % (name, result))
        return result

    # -- what happened ---------------------------------------------------

    def last_ended_well(self):
        """(yes?, why): the last command exited 0, with no error and no stack trace."""
        if self.result is None:
            return False, "no `fcon users` command has been run yet"
        return self.result.ended_well(), self.result

    # -- the install -----------------------------------------------------

    def no_users_yet(self):
        """(yes?, why): the product's database holds no user."""
        count = run_database.user_count(self.world.product_database_url())
        return count == 0, "the database already holds %d user(s)" % count
