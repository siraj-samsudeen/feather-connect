## Why

The dashboard shows a sign-in page that refuses everyone, because there are no users. Every
dashboard page from now on needs a signed-in user, so nothing else on the dashboard can be built
until people can sign in, stay signed in safely, and sign out; and a fresh install needs its first
administrator (issue 16; R10.1, R10.2, R10.4, R10.7, R10.12, R10.13, R15.15, and the parts of
R7.18 that exist).

What people get: whoever installs Feather Connect makes its first administrator with one command,
or with one setting on a host where commands are awkward. Users sign in with a name and a
password, are asked to choose their own password the first time, see who they are and which
environment they are in, and sign out. Guessing passwords is slowed for everyone without ever
locking anyone out, forged forms are refused, and every sign-in, refusal and change is in the
audit log.

## What Changes

- **Users** (issue 16, point 2): each user belongs to one tenant, has one of four roles (viewer,
  operator, developer, administrator) and two grants (deciding holds, seeing personal data),
  and is active or disabled; users are never deleted. Rights are checked in one place, in the
  service layer the dashboard, the API and the command line share.
- **The first administrator** (point 1): `fcon users add <name> --admin`, which asks for the
  password; or `FCON_FIRST_ADMIN=<name>`, which makes that administrator, on a start with no
  users, with a one-time password written to the log once. The first user is always an
  administrator.
- **The command line** (point 2): `fcon users add`, `list`, `disable`, `enable`, `set-role`.
- **Passwords** (point 3): argon2id; 12 to 128 characters, no composition rules, refused when
  common or the user's own name. A password set by someone else works for one sign-in; then the
  user chooses their own before any other page opens.
- **Sessions** (point 4): kept in the database, ended at once by signing out, a new password or
  disabling the user; 12 hours idle or 7 days at most.
- **Forged forms refused** (point 5): a token on every form, and an `Origin` check; a refused
  form gets the "This form has expired" page.
- **The secret key** (point 6): `FCON_SECRET_KEY` is required everywhere; the server refuses to
  start without one, or with one too short. `FCON_SECRET_KEY_PREVIOUS` lets it be replaced
  without signing anyone out. **BREAKING** for anyone running the product: a setting to add.
- **Slowing repeated failures** (point 7): after 3 failures in 15 minutes, by user name or by
  address, each attempt waits longer, up to a minute; nobody is ever locked out.
- **Trusted proxies** (point 8): `FCON_TRUSTED_PROXIES` says whose forwarded headers to believe,
  so the slowing and the audit see the visitor's real address.
- **The pages** (point 9): sign-in (unchanged), the overview (`/`, with the environment's name
  from the new `FCON_ENVIRONMENT`, who is signed in with which role, and Sign out), choose your
  password, and "This form has expired".
- **Always an administrator** (point 10): the last active administrator can't be disabled or
  demoted.
- **Audit** (point 11): every sign-in, refusal, wait, sign-out, password change and change to a
  user, refusals included; passwords, hashes and session ids never.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `users-and-access`: the sign-in page now lets users in. Added: making the first administrator,
  signing in and out, choosing your own password, sessions that end, slowing repeated failures,
  refusing forged forms, managing users from the command line, and always having an
  administrator. Modified: "A refused sign-in gives no hint", which assumed nobody had access.
- `dashboard-basics`: every page a signed-in user sees names the environment and who is signed
  in, with their role (the parts of R7.18 that exist).
- `deployment`: the product's image needs its secret key as well as the database's address.

## Impact

- New tables, through the store and its audit: users, sessions and sign-in attempts, in new
  migrations named by UTC timestamp.
- `packages/fcon-server`: the users service with its rights table, passwords, sessions, the form
  token, the slowing, the real address, the four pages, the first-administrator start-up step.
- `packages/fcon-cli`: `fcon users …`; the settings `FCON_SECRET_KEY`,
  `FCON_SECRET_KEY_PREVIOUS`, `FCON_FIRST_ADMIN`, `FCON_TRUSTED_PROXIES`, `FCON_ENVIRONMENT`.
- One new dependency: `argon2-cffi`.
- `scripts/worktree_env.py` writes a random secret key; `.env.example`, `deploy/.env.example`,
  `deploy/compose.yaml`, `docs/deploy.md` and the image's smoke test name the new settings.
- ADRs for the decisions hard to undo (sessions in the database, argon2id).
- Not in this change (point 12): API tokens, the user-management pages, a "your sessions" list,
  sign-in through an identity provider.
