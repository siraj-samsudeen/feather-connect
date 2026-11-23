# ADR Review Manifest

- Status: completed
- Review date: 2026-11-22

## Review Summary

ADR review completed for this change. Issue 16's choices that are hard to undo once users and
hashes exist are recorded as three repository-level ADRs; the rest of the design's decisions are
in `design.md`.

## In-Force ADRs Reviewed

- [0001 Python 3.14 only](../../../adr/0001-python-3-14-only.md): `argon2-cffi` has wheels for 3.14
- [0003 Pages rendered on the server](../../../adr/0003-pages-rendered-on-the-server.md): the four pages
- [0004 Postgres 18 and later only](../../../adr/0004-postgres-18-only.md): sessions and attempts live there
- [0005 psycopg, sync, plain SQL](../../../adr/0005-psycopg-sync-plain-sql.md)
- [0006 Settings from environment variables](../../../adr/0006-settings-from-environment-variables.md): the five new `FCON_*` settings
- [0007 A strict content policy](../../../adr/0007-strict-content-policy.md): no inline script in the new pages
- [0008 fcon as the technical name](../../../adr/0008-fcon-technical-names.md): `fcon_session`, `fcon_sign_in`, `fcon users`
- [0009 Tenants on every row](../../../adr/0009-tenants-on-every-row.md): users, sessions and attempts carry the tenant
- [0010 Database upgrades](../../../adr/0010-database-upgrades.md): one expand-only migration
- [0011 The store in fcon-server](../../../adr/0011-store-in-fcon-server.md)
- [0012 UUIDv7 ids](../../../adr/0012-uuidv7-ids.md)
- [0013 Concurrency](../../../adr/0013-concurrency.md): the last-administrator check in the change's transaction; the first administrator once, by a unique name
- [0014 The audit log and two roles](../../../adr/0014-audit-log-and-two-roles.md): sign-ins audited through the store; hashes, tokens and session ids as secret columns
- [0015 The container setup](../../../adr/0015-container-setup.md): the secret key and trusted proxies in `deploy/`

None is superseded by this change.

## New Durable ADRs Created

- [0016 A user belongs to one tenant, has one role, and rights are checked in one service layer](../../../adr/0016-users-roles-and-one-rights-check.md) (D-14, for rights)
- [0017 Sessions are kept in the database, with the form token beside them](../../../adr/0017-sessions-in-the-database.md)
- [0018 Passwords are hashed with argon2id, and repeated failures are slowed, never locked](../../../adr/0018-passwords-with-argon2id.md)

`docs/requirements.md` § 11 marks D-14 settled for rights, linking ADR 0016.
