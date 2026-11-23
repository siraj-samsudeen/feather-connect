"""The operator's terminal for users: `fcon users ...` typed at a prompt, the
password typed into it (it reads one line from stdin when that is not a
terminal), and what it printed. The commands, their flags and the texts the
steps rely on live here; the steps only ask questions.

Each command runs against the database of the product the scenario talks to,
with only that address as its setting (support/stack.py, start_fcon).
"""

import re

from pages.database_commands import TRACEBACK, Result
from support import run_database, stack

USERS = "users"
ADD = "add"
DISABLE = "disable"
ENABLE = "enable"
SET_ROLE = "set-role"
LIST = "list"
ADMIN_FLAG = "--admin"
ROLE_FLAG = "--role"
DATABASE_SETTING = "FCON_DATABASE_URL"
# What `fcon users add` says when the password it was given works only once.
WORKS_ONCE = "Their password works for one sign-in; then they choose their own."
# How a command that is refused for a rule ends, and what it says when the
# change would leave no active administrator (design point 10).
REFUSED_EXIT = 2
ONLY_ADMINISTRATOR = "%s is the only administrator; make another one first."
# `fcon users list`: a line of headings, then one line per user, the columns
# apart by two spaces or more.
LIST_HEADINGS = ("NAME", "ROLE", "STATE")
ADMINISTRATOR = "administrator"
ACTIVE = "active"
# The first user's password is their own, so a user with a given password is
# never the first: setup adds this administrator before them.
SETUP_ADMIN = {"name": "setup-admin", "password": "setup-admin-password-0"}
# A user a scenario is signed in as, when it said only their name.
SAMPLE_ADMIN = "ann"
SAMPLE_PASSWORD = "blue-harbour-lamp"  # noqa: S105 - a scenario's sample password
# A user whose password was given them, for a scenario that only needs one.
SAMPLE_NEW_USER = {"name": "ben@example.com", "role": "operator", "password": "given-once-0001"}


class UserCommands:
    def __init__(self, world):
        self.world = world
        self.result = None
        self.results = []  # every command of the scenario, in order
        self.given_passwords = {}  # user -> the password given them, that works once
        self.passwords = {}  # user -> the password they sign in with now

    def _settings(self):
        return {DATABASE_SETTING: self.world.product_database_url()}

    def _run(self, arguments, typed=None):
        # A product the scenario runs elsewhere (the standard setup's containers)
        # gives its own way to run a command there; else it runs here.
        runner = self.world.fcon_runner
        if runner is not None:
            code, out, err, timed_out = runner([USERS, *arguments], typed)
        else:
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
        result = self._run(arguments, typed=password + "\n")
        if result.ended_well():
            self.passwords[name] = password
        return result

    def add_administrator(self, name, password):
        """As setup: an administrator with that password, or an AssertionError
        saying what the command answered."""
        result = self.add(name, password, administrator=True)
        if not result.ended_well():
            raise AssertionError("could not add the administrator %r; %r" % (name, result))
        return result

    def add_with_given_password(self, name, role, password):
        """As setup: a user of that role whose password, given from the command
        line, works once (another administrator is added first when there are
        no users); an AssertionError saying what the command answered."""
        if run_database.user_count(self.world.product_database_url()) == 0:
            self.add_administrator(SETUP_ADMIN["name"], SETUP_ADMIN["password"])
        result = self.add(name, password, role=role)
        if not result.ended_well():
            raise AssertionError("could not add the %s %r; %r" % (role, name, result))
        if WORKS_ONCE not in result.output:
            raise AssertionError("`fcon users add` did not say the password works once (%r); %r" % (WORKS_ONCE, result))
        self.given_passwords[name] = password
        return result

    def add_with_own_password(self, name, role, password):
        """As setup: a user of that role who has already chosen `password`,
        their own: given a password from the command line, then signed in
        with it once to choose theirs."""
        given = "given-%s" % password
        self.add_with_given_password(name, role, given)
        self.world.choose_own_password(name, given, password)
        self.passwords[name] = password

    def administrator(self, name=SAMPLE_ADMIN):
        """(name, password) of an administrator the scenario can sign in as:
        added now, with the sample password, unless the scenario added them."""
        if name not in self.passwords:
            self.add_administrator(name, SAMPLE_PASSWORD)
        return name, self.passwords[name]

    def new_user(self):
        """(name, password) of a user whose password was given them and works
        once: added now, unless the scenario added them."""
        name = SAMPLE_NEW_USER["name"]
        if name not in self.given_passwords:
            self.add_with_given_password(name, SAMPLE_NEW_USER["role"], SAMPLE_NEW_USER["password"])
        return name, self.given_passwords[name]

    def password_of(self, name):
        """The password the user signs in with now, as the scenario set it."""
        if name not in self.passwords:
            raise AssertionError("the scenario set no password for %r" % name)
        return self.passwords[name]

    def disable(self, name):
        """`fcon users disable <name>`; what it answered is in `result`."""
        return self._run([DISABLE, name])

    def enable(self, name):
        """`fcon users enable <name>`; what it answered is in `result`."""
        return self._run([ENABLE, name])

    def set_role(self, name, role):
        """`fcon users set-role <name> <role>`; what it answered is in `result`."""
        return self._run([SET_ROLE, name, role])

    def users(self):
        """`fcon users list`, read: {name: (role, state)}; an AssertionError
        when the command did not end well or its table cannot be read."""
        result = self._run([LIST])
        if not result.ended_well():
            raise AssertionError("`fcon users list` did not end well; %r" % result)
        lines = [line for line in result.output.splitlines() if line.strip()]
        if not lines or tuple(re.split(r"\s{2,}", lines[0].strip())[: len(LIST_HEADINGS)]) != LIST_HEADINGS:
            raise AssertionError("`fcon users list` shows no table headed %r; %r" % (LIST_HEADINGS, result))
        found = {}
        for line in lines[1:]:
            cells = re.split(r"\s{2,}", line.strip())
            if len(cells) < len(LIST_HEADINGS):
                raise AssertionError("cannot read the line %r of `fcon users list`; %r" % (line, result))
            found[cells[0]] = (cells[1], cells[2])
        return found

    def the_only_administrator(self, name):
        """As setup: `name` is an administrator (added now unless the scenario
        added them), and `fcon users list` shows no other active one."""
        self.administrator(name)
        others = [
            user for user, (role, state) in self.users().items()
            if user != name and role == ADMINISTRATOR and state == ACTIVE
        ]  # fmt: skip
        if others:
            raise AssertionError("%r is not the only administrator: so are %r" % (name, others))

    def refused_as_only_administrator(self, name):
        """(yes?, why): the last command was refused, exit REFUSED_EXIT, saying
        that `name` is the only administrator, with no stack trace."""
        result = self.result
        if result is None:
            return False, "no `fcon users` command has been run yet"
        said = ONLY_ADMINISTRATOR % name
        refused = (
            not result.timed_out
            and result.exit_code == REFUSED_EXIT
            and said in result.output + result.errors
            and TRACEBACK not in result.output + result.errors
        )
        return refused, "expected exit %d saying %r; %r" % (REFUSED_EXIT, said, result)

    def is_active_administrator(self, name):
        """(yes?, why): `fcon users list` shows `name` as an active administrator."""
        users = self.users()
        return users.get(name) == (ADMINISTRATOR, ACTIVE), "`fcon users list` shows %r as %r; %r" % (
            name, users.get(name), self.result,
        )  # fmt: skip

    def given_password(self, name):
        """The password the scenario gave that user from the command line."""
        if name not in self.given_passwords:
            raise AssertionError("the scenario gave %r no password from the command line" % name)
        return self.given_passwords[name]

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
