# ADR Review Manifest

- Status: completed
- Review date: 2026-11-21

## Review Summary

ADR review completed for this change. The six decisions of issue 12, point 12, are recorded as
repository-level ADRs; the owner approved the six drafts together, since each was questioned
point by point in the issue. Times, the who-and-when columns and text sorting are in
`design.md` and the conventions of `AGENTS.md` § Project.

## In-Force ADRs Reviewed

- [0001 Python 3.14 only](../../../adr/0001-python-3-14-only.md): unchanged; `uuid.uuid7()` comes
  from 3.14.
- [0002 Three packages](../../../adr/0002-three-packages.md): unchanged; the store goes in
  `fcon-server`, never in the SDK (0011).
- [0003 Pages rendered on the server](../../../adr/0003-pages-rendered-on-the-server.md):
  unchanged.
- [0004 Postgres 18 and later only](../../../adr/0004-postgres-18-only.md): unchanged; the store
  uses 18's `RETURNING OLD.*, NEW.*` and the built-in `pg_c_utf8` collation. The spool, the rest
  of D-02, stays open.
- [0005 psycopg, sync, plain SQL](../../../adr/0005-psycopg-sync-plain-sql.md): unchanged; this
  change adds the pool it promised, with 5 connections by default.
- [0006 Settings from environment variables](../../../adr/0006-settings-from-environment-variables.md):
  unchanged; new `FCON_*` settings only.
- [0007 A strict content policy](../../../adr/0007-strict-content-policy.md): unchanged.
- [0008 fcon as the technical name](../../../adr/0008-fcon-technical-names.md): unchanged; the
  schema is `fcon`.

## New Durable ADRs Created

- [0009 A tenant on every row and call; environments as deployments; tenants ready for sandboxes](../../../adr/0009-tenants-on-every-row.md) (D-05)
- [0010 Database upgrades: our own SQL runner, timestamp names, expand then contract](../../../adr/0010-database-upgrades.md)
- [0011 The store lives in fcon-server, in the fcon schema, never in the SDK](../../../adr/0011-store-in-fcon-server.md)
- [0012 UUIDv7 ids, made in Python](../../../adr/0012-uuidv7-ids.md)
- [0013 Concurrency: row versions, SKIP LOCKED with leases, unique constraints, no transaction across a call](../../../adr/0013-concurrency.md)
- [0014 The audit log is written by the store, and two database roles make it unchangeable](../../../adr/0014-audit-log-and-two-roles.md)

`docs/requirements.md` § 11 marks D-05 settled, linking 0009.
