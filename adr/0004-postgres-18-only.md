# 0004. Postgres 18 and later is the only database, with no extensions

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, point 4 (the first half of catalogue decision D-02)

## Context and Problem Statement

The catalogue's D-02 asks for the required database, and whether it also holds the spool.
Production must need one database with no extensions, so a managed one works (Q-07), on one
machine with no paid licence (Q-15). Supporting several databases, or several major versions,
multiplies the tests and limits the SQL the product can use. Version 18.6 fixed wrong results from
range partitions with a default partition.

## Considered Options

- Postgres 18 and later, and nothing else; no extensions required.
- Postgres from an older major version (16 or 17), which more hosts offer by default.
- Postgres or SQLite, so the local setup needs no database server.

## Decision Outcome

Chosen option: "Postgres 18 and later only", because one database version keeps the SQL and the
tests simple, and 18 is current with the partition fix. The server reads the database's version
when it connects: older than 18, it is not ready, and its log says what it found and what it needs.
Development and CI run 18 on its latest bug-fix release; moving to 19 is a later, ordinary change.
Where the spool lives, the second half of D-02, stays open for the first change that stores data.

### Consequences

- Good, because any managed Postgres 18 works: no extension is needed.
- Good, because the product can use Postgres 18's features without a fallback.
- Bad, because a host's one-click template may still default to an older version; the deployment
  guide (R15.2) has to say to choose the Postgres 18 image.
- Bad, because the local stack needs a database server; development runs it in Docker.
