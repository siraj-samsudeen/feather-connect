## Why

The skeleton connects to Postgres but stores nothing. Sign-in and every data area are about to
add tables, two of them built by developers joining now. If each issue decides for itself how
the database is upgraded, where the store code lives and how ids, times and tenants work, the
product ends up with as many ways as issues. This change decides them once and builds the
foundation they all stand on (issue 12).

What people get: an operator upgrades the database with one command before a new version
starts, and can see what has run and what waits; the server says it is not ready, and why,
while its database is behind; every stored row belongs to a tenant from the first table, so
tenants can never mix later (R14.1); and every change the product stores leaves a record that
cannot be changed (R10.4).

## What Changes

- `fcon db upgrade` applies the waiting database upgrades: plain SQL files in name order, forwards
  only, one process at a time, each recorded with a checksum. `fcon db status` lists what has run
  and what waits, and changes nothing.
- Readiness compares the database with the code: behind or changed means not ready, with a
  two-part message in the log; ahead (after going back to an older version) stays ready.
- The first tables, in the schema `fcon`: the record of applied upgrades, the tenants (with the
  `default` production tenant, ready for sandboxes in M2) and the audit log, partitioned by month
  and protected against change by a trigger.
- The store in `fcon-server`: one transaction helper carrying the tenant and who is acting, ids
  (UUIDv7), one clock, the helper that scopes every query to the tenant and fills the who-and-when
  columns, the row version and the audit record, and the product's own errors for the database's.
- A connection pool with fixed timeouts, `TimeZone = UTC`, a UTF-8 check and an optional switch
  for hosts with a connection pooler in front of Postgres.
- Two database roles: the owner runs upgrades; the app role can only read and write rows, and
  cannot change audit records. One address is enough in development.
- `scripts/worktree_env.py` runs the upgrade after creating the database; tests and the
  acceptance suite run it on their throwaway databases; each test works in a tenant of its own.
- Six ADRs (0009 to 0014), D-05 settled in the catalogue, the M2 sandbox requirement added, and
  new conventions in `AGENTS.md` § Project.

## Capabilities

### New Capabilities

- `database-upgrades`: an operator upgrades the database with one command, sees what has run and
  what waits, and is stopped from running an upgrade that was changed after it ran.

### Modified Capabilities

- `logs-and-health`: ready also means the database matches this version of the product; a
  database that is behind, or holds a changed upgrade, is not ready, and one that is ahead is.

## Impact

- Code: `fcon_server.store` (new, with `migrations/`), `fcon_server.database` and `health`
  (readiness), `fcon_cli` (the `db` commands, new settings `FCON_DATABASE_POOL_SIZE`,
  `FCON_DATABASE_PREPARE`, `FCON_MIGRATION_DATABASE_URL`, and messages in the error helper),
  `scripts/worktree_env.py`, the test fixtures and the acceptance suite's start-up.
- Dependencies: `psycopg-pool`; nothing else new.
- CI: a check that no two upgrade files share a timestamp.
- Docs: `adr/0009` to `adr/0014`, `docs/requirements.md` (D-05, the M2 sandbox requirement),
  `AGENTS.md` § Project (conventions), `.env.example`, `CONTRIBUTING.md` where it names setup.
- Not seen by anyone yet, so pinned by inner tests only: tenant scoping, the row version check
  ("changed by someone else"), the audit record. Their scenarios come with the first page or API
  that edits a row.
- Not in this change: sign-in's tables, the spool and retention (D-02, D-09), the in-memory store
  for running flows locally, row-level security (R14.3), secrets' encryption (R10.3).
