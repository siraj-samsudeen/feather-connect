"""Signing in, and the session it makes (design points 4 and 7, § How it is
built). Every attempt goes the same way, so a made-up name takes as long as
a real one: one argon2id check, against a dummy hash when there is no such
user. Each attempt is a row added through the store, so it is audited.

A session lives in `fcon.session`; the browser holds only its id, 32 random
bytes, of which the database keeps the SHA-256. It ends after 12 hours idle
or 7 days at most, and when its user is disabled. "Last seen" is written at
most once a minute. The role is read fresh with every request.

Signing out ends every session of the user, on every computer.

Not yet here, each with the step that needs it: the slowing of repeated
failures, the clean-up of old attempts."""

import contextlib
import hashlib
import secrets
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from uuid import UUID

from fcon_server.store.clock import Clock
from fcon_server.store.context import Context
from fcon_server.store.errors import ChangedBySomeoneElseError
from fcon_server.store.tables import SESSION, SIGN_IN_ATTEMPT, USER
from fcon_server.store.transaction import Store, Transaction
from fcon_server.users.accounts import ACTIVE
from fcon_server.users.passwords import hash_password, needs_rehash, password_matches
from fcon_server.users.rights import Caller, Role
from fcon_server.users.rules import LONGEST, normal_name

IDLE = timedelta(hours=12)
LONGEST_SESSION = timedelta(days=7)
SEEN_EVERY = timedelta(minutes=1)
NAME_KEPT = 100  # characters of the name tried kept with an attempt: no user's is longer than 64
BY_PASSWORD = "password"  # noqa: S105 - how the session was made, not a secret
SUCCEEDED = "succeeded"
REFUSED = "refused"


@dataclass(frozen=True)
class Attempt:
    name: str
    password: str
    address: str
    user_agent: str | None


@dataclass(frozen=True)
class _User:
    id: UUID
    password_hash: str
    state: str
    row_version: int


@dataclass(frozen=True)
class _Session:
    id: UUID
    row_version: int
    form_token: str
    last_seen_at: datetime
    expires_at: datetime
    user_id: UUID
    name: str
    display_name: str | None
    role: str
    state: str
    must_choose_password: bool


@dataclass(frozen=True)
class SignedIn:
    """Who a request's session belongs to, read fresh with the request."""

    caller: Caller
    session_id: UUID
    user_id: UUID
    name: str
    display_name: str | None
    role: Role
    must_choose_password: bool
    form_token: str


def _id_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _as_user(context: Context, user_id: UUID) -> Context:
    return replace(context, actor=f"user:{user_id}")


_USER_BY_NAME = """
    SELECT id, password_hash, state, row_version FROM fcon.user
    WHERE tenant_id = %(tenant_id)s AND name = %(name)s
"""


def sign_in(store: Store, clock: Clock, context: Context, attempt: Attempt) -> str | None:
    """The new session's id for the cookie, or None when refused."""
    name = normal_name(attempt.name)[:NAME_KEPT]
    with store.transaction(context) as tx:
        user = tx.fetch_one(_User, _USER_BY_NAME, {"name": name})
    # A password longer than any allowed can match none; cut there so a huge
    # one costs no more to check than a long one.
    password = attempt.password[: LONGEST + 1]
    matches = password_matches(user.password_hash if user else None, password)
    tried = {"name": name, "address": attempt.address}
    if user is None or not matches or user.state != ACTIVE:
        with store.transaction(context) as tx:
            tx.insert(SIGN_IN_ATTEMPT, {**tried, "outcome": REFUSED})
        return None
    new_hash = hash_password(password) if needs_rehash(user.password_hash) else None
    session_id = secrets.token_urlsafe(32)
    now = clock.now()
    with store.transaction(_as_user(context, user.id)) as tx:
        tx.insert(SIGN_IN_ATTEMPT, {**tried, "outcome": SUCCEEDED})
        tx.insert(
            SESSION,
            {
                "user_id": user.id,
                "id_hash": _id_hash(session_id),
                "form_token": secrets.token_urlsafe(32),
                "made_by": BY_PASSWORD,
                "address": attempt.address,
                "user_agent": attempt.user_agent,
                "last_seen_at": now,
                "expires_at": now + LONGEST_SESSION,
            },
        )
        if new_hash is not None:
            tx.update(USER, {"id": user.id}, {"password_hash": new_hash}, user.row_version)
    return session_id


_SESSION_BY_ID_HASH = """
    SELECT s.id, s.row_version, s.form_token, s.last_seen_at, s.expires_at,
        u.id AS user_id, u.name, u.display_name, u.role, u.state, u.must_choose_password
    FROM fcon.session s
    JOIN fcon.user u ON u.tenant_id = s.tenant_id AND u.id = s.user_id
    WHERE s.tenant_id = %(tenant_id)s AND u.tenant_id = %(tenant_id)s
        AND s.id_hash = %(id_hash)s AND s.ended_at IS NULL
"""


def _has_ended(session: _Session, now: datetime) -> bool:
    return session.state != ACTIVE or now >= session.expires_at or now - session.last_seen_at >= IDLE


def signed_in(store: Store, clock: Clock, context: Context, session_id: str) -> SignedIn | None:
    """The session the cookie names, if it goes on; one that has run out, or
    whose user is disabled, is ended here. What is written about the session
    is written by its user."""
    now = clock.now()
    with store.transaction(context) as tx:
        session = tx.fetch_one(_Session, _SESSION_BY_ID_HASH, {"id_hash": _id_hash(session_id)})
    if session is None:
        return None
    as_user = _as_user(context, session.user_id)
    key = {"id": session.id}
    if _has_ended(session, now):
        with store.transaction(as_user) as tx, contextlib.suppress(ChangedBySomeoneElseError):
            tx.update(SESSION, key, {"ended_at": now}, session.row_version)  # unless another request ended it first
        return None
    if now - session.last_seen_at >= SEEN_EVERY:
        with store.transaction(as_user) as tx, contextlib.suppress(ChangedBySomeoneElseError):
            tx.update(SESSION, key, {"last_seen_at": now}, session.row_version)  # unless another wrote it first
    role = Role(session.role)
    return SignedIn(
        caller=Caller(as_user, role),
        session_id=session.id,
        user_id=session.user_id,
        name=session.name,
        display_name=session.display_name,
        role=role,
        must_choose_password=session.must_choose_password,
        form_token=session.form_token,
    )


@dataclass(frozen=True)
class _Open:
    id: UUID
    row_version: int


_OPEN_SESSIONS = """
    SELECT id, row_version FROM fcon.session
    WHERE tenant_id = %(tenant_id)s AND user_id = %(user_id)s AND ended_at IS NULL
    ORDER BY id
    FOR UPDATE
"""


def end_sessions(tx: Transaction, user_id: UUID, now: datetime, keep: UUID | None = None) -> None:
    """Ends every open session of the user but `keep`, in the caller's
    transaction, each through the store, so each is audited."""
    for session in tx.fetch_all(_Open, _OPEN_SESSIONS, {"user_id": user_id}):
        if session.id != keep:
            tx.update(SESSION, {"id": session.id}, {"ended_at": now}, session.row_version)


def sign_out(store: Store, clock: Clock, signed_in: SignedIn) -> None:
    """Ends every session of that user, on every computer (design point 4)."""
    with store.transaction(signed_in.caller.context) as tx:
        end_sessions(tx, signed_in.user_id, clock.now())


FOREIGN_ORIGIN = "the form came from another site"
WRONG_FORM_TOKEN = "the form's token is not the session's"  # noqa: S105 - a reason, not a secret


def refuse_form(store: Store, context: Context, session_id: UUID | None, reason: str) -> None:
    """A form refused as expired (design point 5), audited against its
    session, or the tenant when it came with none (decision 3)."""
    with store.transaction(context) as tx:
        tx.refuse(SESSION, "" if session_id is None else str(session_id), reason)
