"""Every request belongs to the tenant `default` until M2 (decision 2)."""

from fcon_server.users.tenant import request_tenant


def test_every_request_belongs_to_the_default_tenant():
    assert request_tenant() == "default"
