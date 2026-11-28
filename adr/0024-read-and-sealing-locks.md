# 0024. The read lock is the open version; sealing takes a transaction lock per partition; the commit number is taken last

- Status: accepted
- Date: 2026-11-28
- Decision-makers: the project owner
- Decided in: issue #31, review rounds 1–3 (locks and commit numbers); built in issue #35

## Context and Problem Statement

One batch read per partition at a time, held for the whole read, which spans many transactions;
events must never wait behind it (Q-01); sealing must be serialized per partition, and several
partitions sealed together without deadlock; commit numbers must become visible in number order,
so reading "as of N" never misses a lower number.

## Considered Options

- The read lock as data: an open version row with a lease, unique per partition; the sealing lock
  as `pg_advisory_xact_lock` per partition, taken in partition id order; the commit number from an
  `UPDATE … RETURNING` of the dataset's progress row as the transaction's last statement.
- Session advisory locks for the read.
- A Postgres sequence for commit numbers.

## Decision Outcome

Chosen option: the first. An open version outlives the worker that held it: its expired lease
lets another worker resume it from its read cursor, or clean it up, and it can be shown on a page.
A session lock would need one connection held for hours and vanish silently with it. A
transaction advisory lock is released by the commit or the rollback, so a crash never leaves it
held. The progress row's lock, taken last, is held only from the numbering to the commit; a
sequence would hand out numbers that become visible out of order, with gaps.

### Consequences

- Good, because no lock outlives its transaction or its lease, whatever process dies.
- Good, because adding a route (build c) takes every partition's sealing lock in id order with
  the same function.
- Bad, because a seal holds its partition's sealing lock for its length: events of that slice
  wait, a few seconds for a million changes.
- Bad, because two partitions whose lock keys collide in the 32-bit hash wait for each other,
  harmlessly.
