"""The dashboard's pages: what each one shows, computed here, and the routes
that answer them. Templates only print what these functions hand them.

There are no users yet, so every sign-in is refused, with the same words for a
wrong name and a wrong password (as the finished sign-in keeps them)."""

from dataclasses import dataclass, field
from typing import Annotated

from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from jinja2 import Environment, PackageLoader, select_autoescape

PRODUCT = "Feather Connect"
FRONT_DOOR_PATH = "/"
SIGN_IN_PATH = "/sign-in"
STYLESHEET_PATH = "/static/feather.css"

REFUSAL = "The user name or password is wrong."
REFUSAL_ID = "sign-in-refused"

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


def render(name: str, view: object, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(templates.get_template(name).render(view=view), status_code=status_code)


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
