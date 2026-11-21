"""ASGI middleware around the whole app, outside FastAPI's own, so that what
they add holds for every response, errors included."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send


class HeadAsGet:
    """Answers HEAD wherever GET is answered: the same status and headers, no
    body. Some uptime monitors check with HEAD, and FastAPI answers 405."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] != "HEAD":
            await self.app(scope, receive, send)
            return

        async def send_without_body(message: Message) -> None:
            if message["type"] == "http.response.body":
                message = {**message, "body": b""}
            await send(message)

        await self.app({**scope, "method": "GET"}, receive, send_without_body)


# The content policy starts from nothing allowed (design decision 3): a page
# that needs more adds exactly that.
SAFETY_HEADERS = [
    (
        b"content-security-policy",
        b"default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'",
    ),
    (b"x-frame-options", b"DENY"),
    (b"x-content-type-options", b"nosniff"),
    (b"referrer-policy", b"same-origin"),
    (b"cache-control", b"no-store"),
]


class SafetyHeaders:
    """Adds the safety headers to every response, errors included."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                message = {**message, "headers": [*message.get("headers", []), *SAFETY_HEADERS]}
            await send(message)

        await self.app(scope, receive, send_with_headers)
