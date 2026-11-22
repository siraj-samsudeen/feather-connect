# 0010. Database upgrades: our own SQL runner, timestamp names, expand then contract

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #12, points 2, 3 and 9

## Context and Problem Statement

R15.3 asks that upgrades change the database forwards only, with no downtime. Several developers
will add tables in parallel worktrees, and long-running branches must be able to merge late. The
store is plain SQL with psycopg (ADR 0005). Someone has to apply the upgrades before a new
version starts, and the server must know whether its database matches it.

## Considered Options

- Plain SQL files applied by a small runner of our own, `fcon db upgrade`, forwards only.
- yoyo-migrations.
- Alembic.
- A separate migration toolchain (Flyway, sqitch).

## Decision Outcome

Chosen option: "our own runner", because it needs no new dependency and does only what the
product needs. Files are named by UTC timestamp and a short name (`20261121T1530Z_add_tenant.sql`);
every file not yet recorded is applied in name order, even one older than the newest applied,
because migrations only add (expand, then contract: a column or table is removed or renamed only
in a later release, once no running code uses it). Each file is recorded with a checksum, and a
file changed after it ran is refused. An advisory lock lets one process upgrade while others
wait; each file runs in a transaction unless its first line says otherwise. The host's pre-deploy
step runs `fcon db upgrade`; the server never changes the database, and is not ready while its
database is behind or holds a changed file. CI refuses two files with one timestamp and an edit
to a file on `main`.

### Consequences

- Good, because two worktrees that each add a migration merge in either order, with no "multiple
  heads" to resolve.
- Good, because the version already running keeps working while an upgrade is applied.
- Bad, because there is no rollback file: a mistake is undone by a new migration.
- Bad, because the runner is ours to maintain; it is kept small and fully tested.
- Rejected: yoyo, whose rollback files go against forwards-only; Alembic, which needs SQLAlchemy
  and reports "multiple heads" when two branches each add one; a separate toolchain, one more
  thing to install on every machine and host.
