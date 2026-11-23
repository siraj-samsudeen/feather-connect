"""Signing in, and the session it makes (design points 4 and 7, § How it is
built). Every attempt goes the same way, so a made-up name takes as long as
a real one: one argon2id check, against a dummy hash when there is no such
user. Each attempt is a row added through the store, so it is audited.

A session lives in `fcon.session`; the browser holds only its id, 32 random
bytes, of which the database keeps the SHA-256. It ends after 12 hours idle
or 7 days at most, and when its user is disabled. "Last seen" is written at
most once a minute. The role is read fresh with every request.

Signing out ends every session of the user, on every computer.

Repeated failures are slowed (point 7): after 3 failures in 15 minutes for
one name from any address, or from one address for any name, each further
attempt waits 1 s, 2 s, 4 s and so on after the last failure, a minute at
most. An attempt during the wait is refused without checking the password
and recorded as `waited`; it is no failure itself, so someone hammering the
form cannot keep the real user out for longer than a minute. A success
clears that name's failures. No account is ever locked. Each sign-in
removes attempts older than a day, at most 100 (decision 3)."""

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
WAITED = "waited"
COUNTED_FOR = timedelta(minutes=15)
FREE_FAILURES = 2  # the third failure starts the wait
LONGEST_WAIT = timedelta(minutes=1)
KEPT_FOR = timedelta(days=1)
REMOVED_AT_ONCE = 100


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


@dataclass(frozen=True)
class _Failure:
    for_name: bool
    for_address: bool
    created_at: datetime


# Failures in the last 15 minutes for the name or from the address, but for
# none of those a success of the same name came after.
_FAILURES = """
    SELECT a.name = %(name)s AS for_name, a.address = %(address)s AS for_address, a.created_at
    FROM fcon.sign_in_attempt a
    WHERE a.tenant_id = %(tenant_id)s AND (a.name = %(name)s OR a.address = %(address)s)
        AND a.outcome = 'refused' AND a.created_at > %(since)s
        AND NOT EXISTS (
            SELECT 1 FROM fcon.sign_in_attempt s
            WHERE s.tenant_id = %(tenant_id)s AND s.name = a.name AND s.outcome = 'succeeded'
                AND s.created_at >= a.created_at
        )
"""

_REMOVE_OLD = """
    DELETE FROM fcon.sign_in_attempt
    WHERE tenant_id = %(tenant_id)s AND id IN (
        SELECT id FROM fcon.sign_in_attempt
        WHERE tenant_id = %(tenant_id)s AND created_at < %(before)s
        LIMIT %(at_most)s
    )
"""


def wait_ends(failures: list[datetime]) -> datetime | None:
    """When the wait these failures bring ends: 1 s after the last of 3, twice
    as long for each one more, a minute at most; None below 3."""
    if len(failures) <= FREE_FAILURES:
        return None
    seconds = 2 ** min(len(failures) - FREE_FAILURES - 1, 6)  # 2 ** 6 passes the minute already
    return max(failures) + min(timedelta(seconds=seconds), LONGEST_WAIT)


def _waiting(failures: list[_Failure], now: datetime) -> bool:
    by_name = wait_ends([failure.created_at for failure in failures if failure.for_name])
    by_address = wait_ends([failure.created_at for failure in failures if failure.for_address])
    return any(ends is not None and now < ends for ends in (by_name, by_address))


# Attempts for one name, or from one address, go one at a time across every
# copy of the server: each takes these locks, the name's then the address's,
# until its transaction ends, so none counts the failures before the one
# ahead of it has recorded its own.
_LOCK_NAME = "SELECT pg_advisory_xact_lock(hashtextextended('sign-in name ' || %(tenant_id)s || ' ' || %(name)s, 0))"
_LOCK_ADDRESS = (
    "SELECT pg_advisory_xact_lock(hashtextextended('sign-in address ' || %(tenant_id)s || ' ' || %(address)s, 0))"
)


def sign_in(store: Store, clock: Clock, context: Context, attempt: Attempt) -> str | None:
    """The new session's id for the cookie, or None when refused."""
    name = normal_name(attempt.name)[:NAME_KEPT]
    tried = {"name": name, "address": attempt.address}
    now = clock.now()
    # A password longer than any allowed can match none; cut there so a huge
    # one costs no more to check than a long one.
    password = attempt.password[: LONGEST + 1]
    with store.transaction(context) as tx:
        tx.execute(_LOCK_NAME, {"name": name})
        tx.execute(_LOCK_ADDRESS, {"address": attempt.address})
        tx.execute(_REMOVE_OLD, {"before": now - KEPT_FOR, "at_most": REMOVED_AT_ONCE})
        failures = tx.fetch_all(_Failure, _FAILURES, {**tried, "since": now - COUNTED_FOR})
        if _waiting(failures, now):
            tx.insert(SIGN_IN_ATTEMPT, {**tried, "outcome": WAITED})
            return None
        user = tx.fetch_one(_User, _USER_BY_NAME, {"name": name})
        matches = password_matches(user.password_hash if user else None, password)
        if user is None or not matches or user.state != ACTIVE:
            tx.insert(SIGN_IN_ATTEMPT, {**tried, "outcome": REFUSED})
            return None
    new_hash = hash_password(password) if needs_rehash(user.password_hash) else None
    session_id = secrets.token_urlsafe(32)
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
        if new_hash is not None:  # unless the user changed meanwhile: the next sign-in redoes it
            with contextlib.suppress(ChangedBySomeoneElseError):
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
