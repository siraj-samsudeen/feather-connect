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
