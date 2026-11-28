# 0023. Record blocks: zstd Parquet, one row each, in a table split by day, with room for encryption and object storage

- Status: accepted
- Date: 2026-11-28
- Decision-makers: the project owner
- Decided in: issue #31, points 4, 10 and 13; built in issue #35

## Context and Problem Statement

A version's records must be stored compactly and typed, be dropped a day at a time when they
expire (point 10), move to object storage in M2 (R3.16) without a format change, and leave room
for personal fields encrypted per person (point 13, R10.16) before erasure is switched on.

## Considered Options

- One Parquet file per block of a few thousand records, zstd, a row per block in a table
  partitioned by day; the hub's own columns prefixed `_fcon_`; a format number in the file's
  metadata; a `location` column; a field-level marker for encrypted fields.
- JSON lines, compressed.
- A row per record.

## Decision Outcome

Chosen option: the first. A block describes itself: its key-value metadata says
`fcon.format = 1`, and a reader refuses a format it does not know, so a later format can sit
beside this one. Deletes travel as records with `_fcon_deleted` true. A personal field encrypted
with a person's key will be a binary column of the same name whose field metadata says
`fcon.encrypted = person-key`, beside `_fcon_person`; until erasure exists, no block has one.
`location` is `database` now, with the Parquet in `data`; in M2 another location holds a name and
`data` is empty. The upgrade makes the day partitions ahead of time, as it makes the audit log's
months; dropping a day is build d's.

### Consequences

- Good, because a day's blocks go with one `DROP`, without bloating the table.
- Good, because the M2 changes (object storage, encrypted fields) add values, not a new format.
- Bad, because a query for one version's blocks names its days, or it probes every partition.
- Bad, because the partitions run out if neither the upgrade nor build d's job makes more;
  readiness warns 30 days before.
