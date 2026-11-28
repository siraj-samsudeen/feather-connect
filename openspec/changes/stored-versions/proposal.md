## Why

Flows will read data from sources, but the product has nowhere to keep what a read produced.
Before the connector SDK, the ledger or any data page can be built, the hub needs to store
each read as a sealed version of its slice, remember each record's state so unchanged records
are never sent again (R3.8), find deletes and moves (R3.2, R3.10), resume an interrupted read
(R3.20), and give the latest state of a slice as of a known point. This change builds that
part of the data model (issue 35, part of the design agreed in issue 31).

What people get: a developer can read records into a dataset and see what each read changed,
in business words ("18 Oct 2026 · Shop 12"), follow one record by its key, and see its
current state; and every later build (deliveries, events, readiness, the SDK) stands on one
store that is fast enough for 20,000 rows a second per worker (Q-02).

## What Changes

- **Partitions:** a row per dataset and slice, identified by its typed values in one canonical
  spelling, with its start and end in UTC, and a business name made from the scheme, with
  labels kept for when a lookup fails (R7.16).
- **Versions and blocks:** each read is an open version until it is sealed, all or nothing. Its
  records are kept in compressed Parquet blocks in a table split by day; deletes travel as
  records marked deleted. A version records its kind (complete, changes-only or starting),
  the records read, added, changed, deleted and unchanged, the package version that made it,
  the shape it was read with, and where the read got to. A version with no changes is not
  stored. A crashed read is resumed from its read cursor, or cleaned up.
- **Record state:** one row per dataset and key with a fingerprint over the declared fields,
  the slice it is in now, the version that last changed it, and present or removed at the
  source, checked inside the sealing transaction.
- **Commit numbers and positions:** one commit number per dataset, given at the very end of
  sealing; the dataset position moves only when a version sealed up to it.
- **The current-state snapshot:** a base as of commit number N plus a tail of later versions,
  always read as of an explicit N; compaction swaps a new base in whole, and a pinned N keeps
  what it needs.
- **Locks:** one open batch read per partition; a short sealing lock per partition, taken in
  partition id order; a dataset-wide lock only for the commit number.
- **A developer's command, `fcon data`:** read a JSON-lines file into a dataset as one version,
  list a dataset's versions, and follow one record, now or as of a commit number. It is how
  the scenarios, and a developer before the SDK exists, reach the stored data.
- **Room for erasure:** the block format marks personal fields encrypted per person (R10.16),
  without encrypting anything yet.
- `pyarrow` as a new dependency, with its ADR. ADRs 0020 to 0024.

## Capabilities

### New Capabilities

- `stored-data`: a read is kept as a sealed version of its slice, with only what changed; each
  record's state is remembered, so deletes and moves are found and unchanged records are left
  out; a developer sees each version's counts, follows a record, and reads the current state
  as of a commit number.

### Modified Capabilities

None.

## How we will know it is broken

- **Logs** (with the tenant and request id, never a record's content): each seal, with its
  dataset, partition, version number, commit number, its counts and how long it took; a seal
  refused (an empty complete read, a second open read of a partition); an open read cleaned
  up; a version marked lost.
- **Measures:** the seal's duration and rows per second are in its log line; a slow seal (over
  10 seconds, when events wait behind its lock) is logged as a warning.
- **Alerts:** none yet. The alert on a stuck or lost version comes with the dashboard's alerts;
  readiness warns, as for the audit log's months, when fewer than 30 days of record-block days
  are made ahead, with its runbook entry.

## Impact

- Code: `fcon_server.data` (new: partitions, blocks, fingerprints, reading, sealing, the
  snapshot), `fcon_server.store` (the new tables, the record-block days made by the upgrade,
  readiness), `fcon_cli` (the `data` commands, their messages in the error helper).
- Database: one expand-only migration adding seven tables in `fcon`.
- Dependencies: `pyarrow` (ADR).
- Depends on issue 34's catalog for the dataset and package version: versions and partitions
  point to them by id; the constraints are added once both builds are on `main`.
- Docs: `adr/0020`–`0024`, `docs/architecture.md` (the stored data), `docs/runbook.md` (the new
  readiness warning).
- Not in this change: deliveries and the ledger (issue 36), the inbox, events, readiness and
  retention's expiry (issue 37), the connector SDK (area 1), encrypting personal fields (M2).
