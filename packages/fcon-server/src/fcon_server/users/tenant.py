"""Every request and command belongs to the tenant `default` until M2
(decision 2): this one function names it, and M2 replaces it."""

DEFAULT_TENANT = "default"


def request_tenant() -> str:
    return DEFAULT_TENANT
