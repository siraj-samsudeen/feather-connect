"""The tenant of every request and command: `default` until M2 (decision 2).

This one function names it, and M2 replaces it.
"""

DEFAULT_TENANT = "default"


def request_tenant() -> str:
    """The tenant the current request or command belongs to: `default` for now."""
    return DEFAULT_TENANT
