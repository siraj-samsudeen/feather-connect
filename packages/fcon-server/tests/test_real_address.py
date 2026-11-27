"""The visitor's real address behind the host's proxy (design point 8).

Forwarded headers are believed only from a trusted proxy.
"""

import pytest
from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import PlainTextResponse
from starlette.routing import Route

from fcon_server.proxies import NotAProxyError, RealAddress, TrustedProxies, real_address, trusted_proxies

CADDY = "172.20.0.3"
VISITOR = "203.0.113.7"


def read(text: str) -> TrustedProxies:
    trusted = trusted_proxies(text)
    assert trusted is not None
    return trusted


def setup_network() -> TrustedProxies:
    return read("172.16.0.0/12")


def test_no_setting_trusts_no_proxy():
    assert trusted_proxies("") is None


def test_a_list_of_addresses_and_ranges_is_read():
    trusted = read(" 10.0.0.1 , 172.16.0.0/12,::1")

    assert [trusted.trusts(address) for address in ("10.0.0.1", "172.20.0.3", "::1", "10.0.0.2")] == [
        True,
        True,
        True,
        False,
    ]


@pytest.mark.parametrize("text", ["not-an-address", "10.0.0.0/33", "10.0.0.1,,", "10.0.0.1/8"])
def test_what_is_not_an_address_or_range_is_refused(text: str):
    with pytest.raises(NotAProxyError, match="FCON_TRUSTED_PROXIES"):
        trusted_proxies(text)


def test_a_peer_not_trusted_is_the_address_whatever_it_forwards():
    assert real_address(VISITOR, f"198.51.100.1, {CADDY}", setup_network()) == VISITOR


def test_a_trusted_peer_names_the_visitor():
    assert real_address(CADDY, VISITOR, setup_network()) == VISITOR


def test_the_last_hop_not_trusted_is_the_visitor():
    forwarded = f"198.51.100.1, {VISITOR}, 172.20.0.9"

    assert real_address(CADDY, forwarded, setup_network()) == VISITOR


def test_a_trusted_peer_that_forwards_nothing_is_the_address():
    assert real_address(CADDY, "", setup_network()) == CADDY


def test_when_every_hop_is_trusted_the_first_is_the_address():
    assert real_address(CADDY, "172.20.0.1, 172.20.0.9", setup_network()) == "172.20.0.1"


def test_a_hop_that_is_not_an_address_ends_the_walk():
    assert real_address(CADDY, "unknown, 172.20.0.9", setup_network()) == "172.20.0.9"


def test_an_ipv4_peer_written_as_ipv6_is_trusted_as_ipv4():
    assert real_address(f"::ffff:{CADDY}", VISITOR, setup_network()) == VISITOR


def test_everyone_trusts_any_peer_but_no_hop():
    """`*`: only the proxy can reach the container, so the peer is it.

    The address it saw is the last hop, whatever the visitor sent before it.
    """
    assert real_address(CADDY, f"198.51.100.1, {VISITOR}", read("*")) == VISITOR


def _client_host(request: Request) -> PlainTextResponse:
    return PlainTextResponse(request.client.host if request.client else "")


def _client(trusted: TrustedProxies | None, warnings: list[str], peer: str = CADDY) -> TestClient:
    app = RealAddress(Starlette(routes=[Route("/", _client_host)]), trusted, lambda: warnings.append("warned"))
    return TestClient(app, client=(peer, 50000))


def test_the_app_sees_the_real_address():
    client = _client(setup_network(), [])

    assert client.get("/", headers={"X-Forwarded-For": VISITOR}).text == VISITOR


def test_every_forwarded_header_counts_in_order():
    client = _client(setup_network(), [])

    answer = client.get("/", headers=[("X-Forwarded-For", VISITOR), ("X-Forwarded-For", "172.20.0.9")])

    assert answer.text == VISITOR


def test_with_no_proxy_trusted_the_app_sees_the_peer():
    client = _client(None, [])

    assert client.get("/", headers={"X-Forwarded-For": VISITOR}).text == CADDY


def test_with_no_proxy_trusted_a_forwarded_request_warns_once():
    warnings: list[str] = []
    client = _client(None, warnings)

    client.get("/", headers={"X-Forwarded-For": VISITOR})
    client.get("/", headers={"X-Forwarded-For": VISITOR})

    assert warnings == ["warned"]


def test_a_request_that_forwards_nothing_does_not_warn():
    warnings: list[str] = []
    client = _client(None, warnings)

    client.get("/")

    assert warnings == []


def test_with_a_proxy_trusted_nothing_warns():
    warnings: list[str] = []
    client = _client(setup_network(), warnings, peer=VISITOR)

    client.get("/", headers={"X-Forwarded-For": "198.51.100.1"})

    assert warnings == []
