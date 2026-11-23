"""The dashboard's pages: what each one shows, computed here, and the routes
that answer them. Templates only print what these functions hand them.

Every route but the open ones sits behind the gate (fcon_server.gate), which
puts the request's context and session on `request.state`. A refused
sign-in uses the same words for a wrong name and a wrong password."""

import hmac
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from pathlib import Path
from typing import Annotated, Any, cast

from fastapi import APIRouter, FastAPI, Form, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, PackageLoader, pass_context, select_autoescape
from jinja2.runtime import Context as TemplateContext
from markupsafe import Markup
from starlette.exceptions import HTTPException

from fcon_server.gate import FORM_TOKEN_FIELD, SESSION_COOKIE
from fcon_server.signing import SIGN_IN_TOKEN_LIFE, SecretKeys, make_sign_in_token, sign_in_token_valid
from fcon_server.store.clock import Clock
from fcon_server.store.context import Context
from fcon_server.store.transaction import Store
from fcon_server.users.choosing import ChoiceProblem, choose_password
from fcon_server.users.rights import Action, require
from fcon_server.users.rules import LONGEST, SHORTEST, PasswordProblem
from fcon_server.users.sessions import LONGEST_SESSION, Attempt, SignedIn, sign_in, sign_out

PRODUCT = "Feather Connect"
OVERVIEW_PATH = "/"
SIGN_IN_PATH = "/sign-in"
SIGN_OUT_PATH = "/sign-out"
CHOOSE_PASSWORD_PATH = "/choose-password"  # noqa: S105 - an address, not a secret
# What a user who must choose a password may open meanwhile.
WHILE_CHOOSING = frozenset({CHOOSE_PASSWORD_PATH, SIGN_OUT_PATH})
STATIC_PATH = "/static"
STATIC_DIRECTORY = Path(__file__).parent / "static"
STYLESHEET_PATH = f"{STATIC_PATH}/fcon.css"
# Open to anyone (decision 1); everything else needs a signed-in user.
OPEN_PATHS = frozenset({SIGN_IN_PATH})
OPEN_PREFIXES = (f"{STATIC_PATH}/",)

SIGN_IN_COOKIE = "fcon_sign_in"
SIGN_IN_TOKEN_FIELD = "sign_in_token"  # noqa: S105 - a field name, not a secret
BACKSLASH = chr(0x5C)  # read by browsers as a slash in an address
NEXT_FIELD = "next"  # the page to go on to after signing in, as the gate names it

REFUSAL = "The user name or password is wrong."
REFUSAL_ID = "sign-in-refused"
NOTHING_YET = "Nothing to watch yet. Flows appear here once they exist."
WHO_SEPARATOR = " · "

logger = logging.getLogger(__name__)

templates = Environment(
    loader=PackageLoader("fcon_server"),
    autoescape=select_autoescape(default=True, default_for_string=True),
)

type Attributes = dict[str, str | None]


@dataclass(frozen=True)
class Site:
    """What every page needs to know about the install: the secret keys, the
    environment's name, and whether cookies are sent over https only."""

    keys: SecretKeys
    environment: str
    secure_cookies: bool


@pass_context
def csrf_field(context: TemplateContext) -> Markup:
    """The hidden field with the session's form token, for every form behind
    sign-in (design point 5)."""
    signed_in: SignedIn = context["request"].state.signed_in
    return Markup('<input type="hidden" name="{}" value="{}">').format(FORM_TOKEN_FIELD, signed_in.form_token)


cast(dict[str, Any], templates.globals)["csrf_field"] = csrf_field


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
    token_field: Attributes
    next_field: Attributes
    alerts: tuple[Alert, ...] = field(default=())
    product: str = PRODUCT
    stylesheet: str = STYLESHEET_PATH


def page_on_this_site(asked: str) -> str:
    """The page asked for, when it is a path on this site: one `/`, not two
    (or a backslash, which browsers read as one), and no space or control
    character, which browsers drop; otherwise "" (design point 9)."""
    if not asked.startswith("/") or asked.startswith("//"):
        return ""
    if any(ord(c) <= 0x20 or ord(c) == 0x7F or c == BACKSLASH for c in asked):
        return ""
    return asked


def page_title(name: str) -> str:
    return f"{name} – {PRODUCT}"


def sign_in_view(user_name: str = "", *, refused: bool = False, token: str = "", next_page: str = "") -> SignInView:
    """The sign-in page, fresh or after a refused sign-in. The password is never
    put back; the user name is, so it need not be typed again. The page to go
    on to is kept only when it is on this site."""
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
        token_field={"type": "hidden", "name": SIGN_IN_TOKEN_FIELD, "value": token},
        next_field={"type": "hidden", "name": NEXT_FIELD, "value": page_on_this_site(next_page)},
        alerts=alerts,
    )


@dataclass(frozen=True)
class OverviewView:
    """The dashboard's first frame: the product, the environment, who is
    signed in with which role, and a way to sign out."""

    title: str
    environment: str
    who: str
    heading: str = "Overview"
    text: str = NOTHING_YET
    sign_out_path: str = SIGN_OUT_PATH
    product: str = PRODUCT
    stylesheet: str = STYLESHEET_PATH


def overview_view(signed_in: SignedIn, environment: str) -> OverviewView:
    return OverviewView(
        title=page_title("Overview"),
        environment=environment,
        who=f"{signed_in.display_name or signed_in.name}{WHO_SEPARATOR}{signed_in.role}",
    )


CHOICE_REFUSED_ID = "choice-refused"
PASSWORD_HINT_ID = "password-hint"  # noqa: S105 - an element's id, not a secret
CHOICE_REFUSALS: dict[PasswordProblem | ChoiceProblem, str] = {
    PasswordProblem.TOO_SHORT: f"The password is too short: use at least {SHORTEST} characters.",
    PasswordProblem.TOO_LONG: f"The password is too long: use at most {LONGEST} characters.",
    PasswordProblem.TOO_COMMON: "The password is too common: it is one of the most used.",
    PasswordProblem.OWN_NAME: "The password is the user's own name: choose another.",
    ChoiceProblem.DIFFERENT: "The two entries are not the same: type the password twice.",
}


@dataclass(frozen=True)
class ChoosePasswordView:
    """The card of the sign-in page, asking for the user's own password, twice."""

    title: str
    lead: str
    hint: str
    form: Attributes
    new_field: Attributes
    again_field: Attributes
    alerts: tuple[Alert, ...] = field(default=())
    hint_id: str = PASSWORD_HINT_ID
    heading: str = "Choose your password"
    product: str = PRODUCT
    stylesheet: str = STYLESHEET_PATH


def choose_password_view(problem: PasswordProblem | ChoiceProblem | None = None) -> ChoosePasswordView:
    """Fresh, or after a refused password, saying which rule it broke; what
    was typed is never put back."""
    refused = problem is not None
    alerts = () if problem is None else (Alert(CHOICE_REFUSED_ID, CHOICE_REFUSALS[problem]),)
    described = f"{PASSWORD_HINT_ID} {CHOICE_REFUSED_ID}" if refused else PASSWORD_HINT_ID
    password: Attributes = {
        "type": "password",
        "autocomplete": "new-password",
        "required": "required",
        "aria-invalid": "true" if refused else None,
    }
    return ChoosePasswordView(
        title=page_title("Choose your password"),
        lead="The one you were given works only once.",
        hint=f"At least {SHORTEST} characters.",
        form={"method": "post", "action": CHOOSE_PASSWORD_PATH},
        new_field={"id": "new-password", "name": "new_password", "aria-describedby": described, **password},
        again_field={"id": "password-again", "name": "password_again", **password},
        alerts=alerts,
    )


@dataclass(frozen=True)
class MessageView:
    """A page that says one thing and leads on: not found, an error, an expired form."""

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
        link_text="Go to the overview",
        link_href=OVERVIEW_PATH,
    )


def error_view() -> MessageView:
    """Never says what failed: that goes to the server's log only."""
    return MessageView(
        title=page_title("Something went wrong"),
        heading="Something went wrong",
        text="The server could not answer this request. Try again in a moment.",
    )


def form_expired_view() -> MessageView:
    return MessageView(
        title=page_title("Form expired"),
        heading="This form has expired",
        text="Reload the page and try again.",
        link_text="Go to the overview",
        link_href=OVERVIEW_PATH,
    )


def render(name: str, view: object, status_code: int = 200, request: Request | None = None) -> HTMLResponse:
    html = templates.get_template(name).render(view=view, request=request)
    return HTMLResponse(html, status_code=status_code)


def error_page() -> HTMLResponse:
    return render("message.html", error_view(), status_code=500)


def form_expired_page() -> HTMLResponse:
    return render("message.html", form_expired_view(), status_code=403)


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
    return error_page()


def install_error_pages(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_error)
    app.add_exception_handler(Exception, server_error)


# -- what the routes read from the app and the request ---------------------------


def _site(request: Request) -> Site:
    return cast(Site, request.app.state.site)


def _store(request: Request) -> Store:
    return cast(Store, request.app.state.store)


def _clock(request: Request) -> Clock:
    return cast(Clock, request.app.state.clock)


def _context(request: Request) -> Context:
    return cast(Context, request.state.context)


def _signed_in(request: Request) -> SignedIn:
    return cast(SignedIn, request.state.signed_in)


def _same(given: str, expected: str) -> bool:
    return hmac.compare_digest(given.encode(), expected.encode())


def _sign_in_token(request: Request) -> str:
    """The token of the visitor's sign-in cookie while it is valid, so two
    tabs share it; a new one otherwise."""
    site, now = _site(request), _clock(request).now()
    kept = request.cookies.get(SIGN_IN_COOKIE, "")
    return kept if sign_in_token_valid(site.keys, kept, now) else make_sign_in_token(site.keys, now)


def _cookie_options(request: Request, path: str, life: timedelta) -> dict[str, Any]:
    return {
        "max_age": int(life.total_seconds()),
        "path": path,
        "secure": _site(request).secure_cookies,
        "httponly": True,
        "samesite": "lax",
    }


def _sign_in_form(request: Request, view: SignInView) -> HTMLResponse:
    token = str(view.token_field["value"])
    response = render("sign_in.html", view)
    response.set_cookie(SIGN_IN_COOKIE, token, **_cookie_options(request, SIGN_IN_PATH, SIGN_IN_TOKEN_LIFE))
    return response


def router() -> APIRouter:
    routes = APIRouter()

    @routes.get(OVERVIEW_PATH)
    def overview(request: Request) -> HTMLResponse:
        signed_in = _signed_in(request)
        require(_store(request), signed_in.caller, Action.SEE_OVERVIEW)
        return render("overview.html", overview_view(signed_in, _site(request).environment), request=request)

    @routes.get(SIGN_IN_PATH)
    def sign_in_page(request: Request) -> HTMLResponse:
        next_page = request.query_params.get(NEXT_FIELD, "")
        return _sign_in_form(request, sign_in_view(token=_sign_in_token(request), next_page=next_page))

    @routes.post(SIGN_IN_PATH)
    def sign_in_form(
        request: Request,
        username: Annotated[str, Form()] = "",
        password: Annotated[str, Form()] = "",
        sign_in_token: Annotated[str, Form()] = "",
        next_page: Annotated[str, Form(alias=NEXT_FIELD)] = "",
    ) -> Response:
        """A form without the token of the visitor's own sign-in cookie is
        refused as expired (login CSRF). A refused sign-in gets the form
        again, with the message: 200, as the page shown is the sign-in form."""
        site, clock = _site(request), _clock(request)
        kept = request.cookies.get(SIGN_IN_COOKIE, "")
        if not (_same(sign_in_token, kept) and sign_in_token_valid(site.keys, sign_in_token, clock.now())):
            return form_expired_page()
        address = request.client.host if request.client else ""
        attempt = Attempt(username, password, address, request.headers.get("user-agent"))
        session_id = sign_in(_store(request), clock, _context(request), attempt)
        if session_id is None:
            return _sign_in_form(
                request, sign_in_view(username, refused=True, token=sign_in_token, next_page=next_page)
            )
        response = RedirectResponse(page_on_this_site(next_page) or OVERVIEW_PATH, status_code=303)
        response.set_cookie(SESSION_COOKIE, session_id, **_cookie_options(request, "/", LONGEST_SESSION))
        response.delete_cookie(SIGN_IN_COOKIE, path=SIGN_IN_PATH)
        return response

    @routes.get(CHOOSE_PASSWORD_PATH)
    def choose_password_page(request: Request) -> Response:
        """Only while the user must choose one: changing one's own password
        later asks for the old one, on a page of its own."""
        if not _signed_in(request).must_choose_password:
            return RedirectResponse(OVERVIEW_PATH, status_code=303)
        return render("choose_password.html", choose_password_view(), request=request)

    @routes.post(CHOOSE_PASSWORD_PATH)
    def choose_password_form(
        request: Request,
        new_password: Annotated[str, Form()] = "",
        password_again: Annotated[str, Form()] = "",
    ) -> Response:
        signed_in = _signed_in(request)
        if not signed_in.must_choose_password:
            return RedirectResponse(OVERVIEW_PATH, status_code=303)
        problem = choose_password(_store(request), _clock(request), signed_in, new_password, password_again)
        if problem is not None:
            return render("choose_password.html", choose_password_view(problem), request=request)
        return RedirectResponse(OVERVIEW_PATH, status_code=303)

    @routes.post(SIGN_OUT_PATH)
    def sign_out_form(request: Request) -> Response:
        """Ends every session of the user; the gate has checked the form's token."""
        sign_out(_store(request), _clock(request), _signed_in(request))
        response = RedirectResponse(SIGN_IN_PATH, status_code=303)
        response.delete_cookie(SESSION_COOKIE, path="/")
        return response

    return routes
