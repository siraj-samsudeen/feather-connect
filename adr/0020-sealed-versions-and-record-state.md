# 0020. Stored data: sealed versions of partitions, one record-state row per key, commit numbers per dataset

- Status: accepted
- Date: 2026-11-28
- Decision-makers: the project owner
- Decided in: issue #31, points 3, 4, 5 and 8 with review rounds 1–3; built in issue #35

## Context and Problem Statement

A flow's read must be kept so it can be delivered to many routes, resumed after a crash, compared
with what came before, and read back as the latest state of a slice. Q-02 asks for 20,000 rows a
second per worker, Q-03 for 5 million records a day on the smallest deployment, and Q-07 for one
database with no extensions.

## Considered Options

- A partition row per slice; each read an open version sealed all or nothing; records in
  compressed blocks; one record-state row per dataset and key, compared inside sealing; one commit
  number per dataset given at the end of sealing; a current-state snapshot as a base plus a tail.
- A Postgres row per record, compared with the previous version's records.
- An event log of every record change, with state derived from it.

## Decision Outcome

Chosen option: the first, because comparing against one row per key finds unchanged records,
deletes and moves without reading old versions, blocks keep a read of millions small and fast, and
commit numbers given last make "as of N" exact. A speed prototype measured it against Q-02 before
anything was built on it; its method and numbers are in the change's design (`stored-versions`).

Record state is created with half of each page left free (`fillfactor = 50`), so a seal's updates,
which change no indexed column, are made in place without new index entries: measured four times
faster on a million changed records, for about 1.7 times the space.

### Consequences

- Good, because every later build (deliveries, events, readiness, the SDK) reads one model: a
  sealed version of a partition, numbered in its slice and in its dataset.
- Good, because a read that dies leaves an open version to resume or clean up, never half a version.
- Bad, because record state grows with every key ever seen until an operator purge (level 3 in
  issue 31), and takes more space for its free half-pages.
- Bad, because the snapshot needs a compaction job, or reads grow with the tail.
