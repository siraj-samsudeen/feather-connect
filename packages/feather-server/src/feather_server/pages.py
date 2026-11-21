"""The dashboard's pages: what each one shows, computed here, and the routes
that answer them. Templates only print what these functions hand them.

There are no users yet, so every sign-in is refused, with the same words for a
wrong name and a wrong password (as the finished sign-in keeps them)."""

import logging
from dataclasses import dataclass, field
from typing import Annotated, cast

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, PackageLoader, select_autoescape
from starlette.exceptions import HTTPException

PRODUCT = "Feather Connect"
FRONT_DOOR_PATH = "/"
SIGN_IN_PATH = "/sign-in"
STYLESHEET_PATH = "/static/feather.css"

REFUSAL = "The user name or password is wrong."
REFUSAL_ID = "sign-in-refused"

logger = logging.getLogger(__name__)

templates = Environment(
    loader=PackageLoader("feather_server"),
    autoescape=select_autoescape(default=True, default_for_string=True),
)

type Attributes = dict[str, str | None]


@dataclass(frozen=True)
class Alert:
    id: str
    text: str


@dataclass(frozen=True)
class SignInView:
    title: str
    lead: str
    form: Attributes
    user_field: Attributes
    password_field: Attributes
    alerts: tuple[Alert, ...] = field(default=())
    product: str = PRODUCT
    stylesheet: str = STYLESHEET_PATH


def page_title(name: str) -> str:
    return f"{name} – {PRODUCT}"


def sign_in_view(user_name: str = "", *, refused: bool = False) -> SignInView:
    """The sign-in page, fresh or after a refused sign-in. The password is never
    put back; the user name is, so it need not be typed again."""
    alerts = (Alert(REFUSAL_ID, REFUSAL),) if refused else ()
    invalid = "true" if refused else None
    return SignInView(
        title=page_title("Sign-in failed" if refused else "Sign in"),
        lead="Sign in to continue",
        form={"method": "post", "action": SIGN_IN_PATH, "aria-describedby": REFUSAL_ID if refused else None},
        user_field={
            "id": "user-name",
            "name": "username",
            "type": "text",
            "autocomplete": "username",
            "required": "required",
            "value": user_name,
            "aria-invalid": invalid,
        },
        password_field={
            "id": "password",
            "name": "password",
            "type": "password",
            "autocomplete": "current-password",
            "required": "required",
            "aria-invalid": invalid,
        },
        alerts=alerts,
    )


@dataclass(frozen=True)
class MessageView:
    """A page that says one thing and leads on to sign-in: not found, an error."""

    title: str
    heading: str
    text: str
    link_text: str = "Go to sign in"
    link_href: str = SIGN_IN_PATH
    product: str = PRODUCT
    stylesheet: str = STYLESHEET_PATH


def not_found_view() -> MessageView:
    """Never names the address asked for: it is the visitor's own text."""
    return MessageView(
        title=page_title("Page not found"),
        heading="Page not found",
        text="There is no page at this address.",
    )


def error_view() -> MessageView:
    """Never says what failed: that goes to the server's log only."""
    return MessageView(
        title=page_title("Something went wrong"),
        heading="Something went wrong",
        text="The server could not answer this request. Try again in a moment.",
    )


def render(name: str, view: object, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(templates.get_template(name).render(view=view), status_code=status_code)


async def http_error(request: Request, exc: Exception) -> Response:
    """An unknown address gets the not-found page; other refusals (405) keep
    FastAPI's own answer."""
    exc = cast(HTTPException, exc)  # registered for HTTPException alone
    if exc.status_code == 404:
        return render("message.html", not_found_view(), status_code=404)
    return await http_exception_handler(request, exc)


async def server_error(request: Request, exc: Exception) -> Response:
    """A bug: one line here; Uvicorn logs the traceback as the error goes on up."""
    logger.error("a bug: %s %s failed inside the server (%s)", request.method, request.url.path, type(exc).__name__)
    return render("message.html", error_view(), status_code=500)


def install_error_pages(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, server_error)


def router() -> APIRouter:
    routes = APIRouter()

    @routes.get(FRONT_DOOR_PATH)
    def front_door() -> RedirectResponse:
        """Nobody is signed in yet, so the front door leads to sign-in."""
        return RedirectResponse(SIGN_IN_PATH, status_code=303)

    @routes.get(SIGN_IN_PATH)
    def sign_in_page() -> HTMLResponse:
        return render("sign_in.html", sign_in_view())

    @routes.post(SIGN_IN_PATH)
    def sign_in(username: Annotated[str, Form()] = "") -> HTMLResponse:
        """Every attempt is refused: the form again, with the message. 200, as
        the page shown is the sign-in form itself."""
        return render("sign_in.html", sign_in_view(username, refused=True))

    return routes
