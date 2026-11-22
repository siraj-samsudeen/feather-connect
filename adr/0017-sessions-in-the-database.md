# 0017. Sessions are kept in the database, with the form token beside them

- Status: accepted
- Date: 2026-11-22
- Decision-makers: the project owner
- Decided in: issue #16, points 4 and 5

## Context and Problem Statement

The dashboard needs a secure session and a token on every form against forged requests (R10.7).
Signing out, a new password, or disabling a user must end every session of that user at once
(R10.12). Several server copies may serve the same users, behind a proxy.

## Considered Options

- Sessions in the database (`fcon.session`, tenant-scoped): the browser holds only a random id of
  32 bytes in the cookie `fcon_session`; the database stores its SHA-256 hash, the user, when and
  how it was made, the address and user agent, when it was last seen, and a random form token.
- Signed cookies holding the user and an expiry, with no server state.
- Sessions in a separate store, such as Redis.

## Decision Outcome

Chosen option: "sessions in the database", because only the server can end a session at once, and
Postgres is already the one database (ADR 0004), shared by every server copy. A session ends after
12 hours idle or 7 days at most; a new id at every sign-in. The cookie is `HttpOnly`,
`SameSite=Lax`, `Path=/`, and `Secure` unless the server listens only on its own machine. Every
form carries the session's token, and every POST, PUT, PATCH and DELETE is checked against it;
an `Origin` naming another site is refused first. The sign-in form, made before any session, has
its own token in a short-lived cookie signed with `FCON_SECRET_KEY`.

### Consequences

- Good, because signing out, a new password and disabling a user end sessions everywhere at once,
  and a stolen database copy holds no usable session id.
- Good, because the form token needs no second secret: it lives and ends with the session.
- Bad, because every page reads the session from the database: one indexed lookup; "last seen"
  is written at most once a minute.
- Rejected: signed cookies, which can't be ended from the server before they expire; Redis, a
  second system to run, back up and secure for one table's worth of rows.
