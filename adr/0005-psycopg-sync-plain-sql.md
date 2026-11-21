# 0005. psycopg, with sync calls and plain SQL; no object mapper

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, point 4

## Context and Problem Statement

The server, the workers and the command line all reach the same database. Postgres is the only
database (ADR 0004), so nothing needs to hide which database it is. The product's hard parts (the
spool, the ledger, partitions) depend on exact SQL: locking, ordering, upserts. Async code would
split every store function into two flavours, or force every caller to be async.

## Considered Options

- psycopg 3, sync calls, plain SQL in one store layer, and psycopg's connection pool.
- SQLAlchemy as an object mapper over psycopg.
- An async driver (asyncpg or psycopg's async API) with async routes throughout.

## Decision Outcome

Chosen option: "psycopg 3, sync, plain SQL", because one store serves the server, the workers and
the command line, the SQL that matters is written and reviewed as SQL, and FastAPI runs plain
routes in its thread pool. An async route is used only where a later page needs one. The
database address goes to psycopg unchanged, so options such as `sslmode=require` work. The pool
arrives with the first change that stores data; until then each check opens its own connection
(this change's design, decision 2).

### Consequences

- Good, because there is one way to reach the database, with no mapper to learn or tune.
- Good, because sync code is simpler to test and to read.
- Bad, because every query and every result shape is written by hand, and kept in one store layer.
- Bad, because a request waiting on the database holds a thread; the pool's size is decided with
  the first store.
