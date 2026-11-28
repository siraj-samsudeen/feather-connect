# ADR Review Manifest

- Status: completed
- Review date: 2026-11-28

## Review Summary

ADR review completed for this change. Issue 31's choices for the stored half of the data model
that are hard to undo once data exists are recorded as five repository-level ADRs; the rest of
the design's decisions are in `design.md`. ADR 0019 is issue 34's (the catalog), built at the
same time.

## In-Force ADRs Reviewed

- [0001 Python 3.14 only](../../../adr/0001-python-3-14-only.md): `pyarrow` has wheels for 3.14
- [0002 Three packages](../../../adr/0002-three-packages.md): the stored data lives in `fcon-server`; the SDK holds no database code
- [0004 Postgres 18 and later only](../../../adr/0004-postgres-18-only.md): blocks in Postgres, no extension (Q-07)
- [0005 psycopg, sync, plain SQL](../../../adr/0005-psycopg-sync-plain-sql.md): sealing is plain SQL, `COPY` into a temporary table
- [0008 fcon as the technical name](../../../adr/0008-fcon-technical-names.md): `fcon data`, `fcon.format`, `_fcon_` columns
- [0009 Tenants on every row](../../../adr/0009-tenants-on-every-row.md): every new table
- [0010 Database upgrades](../../../adr/0010-database-upgrades.md): one expand-only migration; the upgrade also makes record-block days
- [0011 The store in fcon-server](../../../adr/0011-store-in-fcon-server.md)
- [0012 UUIDv7 ids](../../../adr/0012-uuidv7-ids.md)
- [0013 Concurrency](../../../adr/0013-concurrency.md): leases with `SKIP LOCKED` for open reads; detailed by 0024
- [0014 The audit log and two roles](../../../adr/0014-audit-log-and-two-roles.md): the per-row audit is narrowed for bulk data rows by 0022

None is superseded: 0022 narrows convention 14's per-row audit for bulk data rows only, and 0024
applies 0013 to reads and sealing.

## New Durable ADRs Created

- [0020 Stored data: sealed versions of partitions, one record-state row per key, commit numbers per dataset](../../../adr/0020-sealed-versions-and-record-state.md)
- [0021 pyarrow reads and writes the record blocks](../../../adr/0021-pyarrow-for-record-blocks.md)
- [0022 Bulk data rows are written set-based and audited once per sealed version](../../../adr/0022-bulk-data-rows-audited-per-version.md)
- [0023 Record blocks: zstd Parquet, one row each, in a table split by day](../../../adr/0023-record-blocks-parquet-by-day.md)
- [0024 The read lock is the open version; sealing takes a transaction lock per partition; the commit number is taken last](../../../adr/0024-read-and-sealing-locks.md)
