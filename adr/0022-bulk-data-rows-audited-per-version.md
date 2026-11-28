# 0022. Bulk data rows are written set-based and audited once per sealed version

- Status: accepted
- Date: 2026-11-28
- Decision-makers: the project owner
- Decided in: issue #35's build (the speed prototype)

## Context and Problem Statement

Convention 14 says rows are written through the store's helpers, which write an audit record for
each (ADR 0014). Sealing writes thousands to millions of record-state rows and blocks. Written row
by row with an audit record each, sealing would be many times slower than Q-02 allows, and the
audit log would hold a copy of every record change for good.

## Considered Options

- Set-based SQL inside the sealing transaction, through a store helper that binds the tenant, the
  actor and the clock's time; one audit record per sealed version.
- Every row through `tx.insert` and `tx.update`, each audited.
- Data rows not audited at all.

## Decision Outcome

Chosen option: set-based writes with one audit record per version, because the version's audit
record (its change to sealed, with its counts) says who sealed what and when, and the version and
its blocks say exactly which records changed. The rule applies only to the data rows that sealing
and compaction write in bulk: record state, record blocks and snapshot blocks. Every other row,
the version and partition rows included, goes through the store's helpers as before. The
who-and-when columns are still filled from the context and the clock, never typed by hand in a
query, and the tenant is still checked by the store.

### Consequences

- Good, because sealing a million changes takes seconds, not hours.
- Good, because the audit log stays a log of what people and jobs did.
- Bad, because a record's history is read from versions and blocks, not from the audit log; when
  a version's blocks expire (build d), its row stays and says so.
