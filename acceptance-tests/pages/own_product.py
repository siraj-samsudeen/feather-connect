"""A product the scenario starts itself, as an operator does, with settings
of its own: the environment it names, the secret keys it signs with. Every
setting name lives here; the steps only say what the operator does.

It runs on this machine, on a free port (support/stack.py, start_server):
on a database of the scenario's own, or on the run's when the scenario has
already set up users there.
"""

import secrets

from support import stack

ENVIRONMENT_SETTING = "FCON_ENVIRONMENT"
SECRET_KEY_SETTING = stack.SECRET_KEY_SETTING
PREVIOUS_SECRET_KEY_SETTING = "FCON_SECRET_KEY_PREVIOUS"


def _new_key():
    return secrets.token_urlsafe(32)


class OwnProduct:
    def __init__(self, world):
        self.world = world
        self.secret_key = None

    def start_in_environment(self, name):
        """The product, started now on a database of the scenario's own,
        naming its environment `name`; the scenario talks to it."""
        self.world.name_in_settings(ENVIRONMENT_SETTING, name)
        self.world.start_own_product()

    def start_with_a_secret_key(self):
        """The product, started now on the run's database (where the scenario
        added its users) with a secret key of its own; the scenario talks to it."""
        self.secret_key = _new_key()
        self.world.name_in_settings(SECRET_KEY_SETTING, self.secret_key)
        self.world.start_own_product(on_run_database=True)

    def restart_with_a_new_secret_key(self):
        """Stops the product and starts it again at the same address, with a
        new secret key and the old one named as previous."""
        if self.secret_key is None:
            raise RuntimeError("the product was not started with a secret key of the scenario's")
        old, self.secret_key = self.secret_key, _new_key()
        self.world.name_in_settings(SECRET_KEY_SETTING, self.secret_key)
        self.world.name_in_settings(PREVIOUS_SECRET_KEY_SETTING, old)
        self.world.restart_own_product()
