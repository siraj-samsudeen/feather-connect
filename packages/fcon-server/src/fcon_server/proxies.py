"""The visitor's real address behind the host's proxy (design point 8).

`X-Forwarded-For` is believed only from a peer that FCON_TRUSTED_PROXIES trusts:
then the real address is the last hop in it that is not a trusted proxy. `*`
trusts any peer, for hosts where only the proxy can reach the container, but no
hop in the header: the address is the one that proxy saw. Without the setting
the header is ignored, and the first request carrying it is reported once, so
the operator learns the setting exists.
"""

import ipaddress
from collections.abc import Callable
from dataclasses import dataclass

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

SETTING = "FCON_TRUSTED_PROXIES"
EVERYONE = "*"
FORWARDED_FOR = "x-forwarded-for"

type Address = ipaddress.IPv4Address | ipaddress.IPv6Address
type Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@dataclass(frozen=True)
class TrustedProxies:
    """The proxies FCON_TRUSTED_PROXIES names; `everyone` is its `*`, trusting any peer."""

    networks: tuple[Network, ...]
    everyone: bool = False

    def trusts(self, address: str) -> bool:
        """Whether a hop at `address` is a trusted proxy."""
        parsed = _address(address)
        return parsed is not None and any(parsed in network for network in self.networks)

    def trusts_peer(self, address: str) -> bool:
        """Whether the peer at `address` is trusted to forward: any peer under `*`."""
        return self.everyone or self.trusts(address)


class NotAProxyError(ValueError):
    """An item of FCON_TRUSTED_PROXIES that is not an address or a range."""

    def __init__(self, item: str) -> None:
        super().__init__(f"{SETTING} is not a list of addresses or ranges: {item!r}")
        self.item = item


def _address(text: str) -> Address | None:
    """The IP address in `text`, an IPv4-mapped one as IPv4, or None when it is not an address."""
    try:
        parsed = ipaddress.ip_address(text.strip())
    except ValueError:
        return None
    if isinstance(parsed, ipaddress.IPv6Address) and parsed.ipv4_mapped is not None:
        return parsed.ipv4_mapped
    return parsed


def trusted_proxies(text: str) -> TrustedProxies | None:
    """FCON_TRUSTED_PROXIES read: addresses or ranges, comma-separated, or `*`; None when unset.

    Raises NotAProxyError for anything else.
    """
    if not text.strip():
        return None
    networks: list[Network] = []
    everyone = False
    for item in (part.strip() for part in text.split(",")):
        if item == EVERYONE:
            everyone = True
            continue
        try:
            networks.append(ipaddress.ip_network(item))
        except ValueError:
            raise NotAProxyError(item) from None
    return TrustedProxies(tuple(networks), everyone)


def real_address(peer: str, forwarded_for: str, trusted: TrustedProxies) -> str:
    """The visitor's address: the peer's, unless the peer is trusted.

    Then it is the last hop of `forwarded_for` that is not trusted, walking from
    the right. A hop that is not an address ends the walk at the one before it.
    """
    if not trusted.trusts_peer(peer):
        return peer
    address = peer
    for hop in reversed([hop.strip() for hop in forwarded_for.split(",") if hop.strip()]):
        if _address(hop) is None:
            break
        address = hop
        if not trusted.trusts(hop):
            break
    return address


class RealAddress:
    """Puts the visitor's real address in the request's `client`.

    The slowing, the session row and the audit all read it there. With no proxy
    trusted, `on_untrusted_forwarding` is called on the first request that
    carries X-Forwarded-For, once per process.
    """

    def __init__(
        self, app: ASGIApp, trusted: TrustedProxies | None, on_untrusted_forwarding: Callable[[], None]
    ) -> None:
        self.app = app
        self.trusted = trusted
        self.on_untrusted_forwarding = on_untrusted_forwarding
        self.warned = False

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Pass an http request on with its real address as its client; with no proxy trusted, as it is."""
        client = scope.get("client")
        if scope["type"] != "http" or client is None:
            await self.app(scope, receive, send)
            return
        forwarded_for = ",".join(Headers(scope=scope).getlist(FORWARDED_FOR))
        if self.trusted is None:
            if forwarded_for and not self.warned:
                self.warned = True
                self.on_untrusted_forwarding()
            await self.app(scope, receive, send)
            return
        peer, port = client
        await self.app({**scope, "client": (real_address(peer, forwarded_for, self.trusted), port)}, receive, send)
