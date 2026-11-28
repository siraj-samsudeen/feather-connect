## 1. First-time setup — `acceptance-tests/` exists (issue 4); only what this change adds

- [x] 1.1 A page object for the developer's terminal runs `fcon data read`, `fcon data versions` and `fcon data record` against the run's database with a JSON-lines file it writes for the scenario, and keeps their output and exit code; the texts the steps rely on live in it
- [x] 1.2 A scenario's dataset: the step that gives a dataset puts its catalog entry in the run's database (the one thing the product cannot yet be made to do from outside, until packages are installed), on a stand-in catalog table when issue 34's is not there yet

## 2. Step definitions — one task per pending step; each = fails for the right reason → implement → passes → commit

### Versions and counts

- [ ] 2.1 stored-data: Given a dataset of orders, split by shop and by day — red → green → commit
- [ ] 2.2 stored-data: When the user reads orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026 (and its Given form) — red → green → commit
- [ ] 2.3 stored-data: Then the slice "…" has N version(s) — red → green → commit
- [ ] 2.4 stored-data: Then version N counts R records read: A added, C changed, D deleted and U unchanged (and "its version N") — red → green → commit

### Unchanged records

- [ ] 2.5 stored-data: When the user reads the same three orders again, with order 1002's amount changed — red → green → commit
- [ ] 2.6 stored-data: And version 2 holds order 1002 only — red → green → commit
- [ ] 2.7 stored-data: When the user reads the same three orders again, unchanged — red → green → commit
- [ ] 2.8 stored-data: Then the user is told nothing changed — red → green → commit

### Last copy, deletes and empty reads

- [ ] 2.9 stored-data: When the user reads order 1001 … twice in one read, first with an amount of 10.00, then of 12.00 — red → green → commit
- [ ] 2.10 stored-data: Then following order 1001 shows an amount of 12.00 — red → green → commit
- [ ] 2.11 stored-data: When the user reads that slice in full, and it returns orders 1001 and 1002 only — red → green → commit
- [ ] 2.12 stored-data: Then version 2 is a complete read — red → green → commit
- [ ] 2.13 stored-data: And following order 1003 shows it was removed at the source — red → green → commit
- [ ] 2.14 stored-data: When the user reads that slice in full, and it returns no orders — red → green → commit
- [ ] 2.15 stored-data: Then the read is refused, and the user is told the slice would be emptied — red → green → commit
- [ ] 2.16 stored-data: Given a dataset of orders, split by shop and by day, that allows an empty slice — red → green → commit

### Moves and following a record

- [ ] 2.17 stored-data: When the user reads order 1002 again, now ordered on 19 Oct 2026 — red → green → commit
- [ ] 2.18 stored-data: And following order 1002 shows it in the slice "Shop 12 · 19 Oct 2026" — red → green → commit
- [ ] 2.19 stored-data: And the user has read order 1002 again, with its amount changed to 12.00 — red → green → commit
- [ ] 2.20 stored-data: When the user follows order 1002 — red → green → commit
- [ ] 2.21 stored-data: Then it shows an amount of 12.00, in the slice "Shop 12 · 18 Oct 2026" — red → green → commit
- [ ] 2.22 stored-data: And it was last changed by version 2 — red → green → commit

### As of a commit

- [ ] 2.23 stored-data: And the user has read orders 1001, 1002 and 1003 …, each for 10.00 — red → green → commit
- [ ] 2.24 stored-data: When the user follows order 1002 as of commit 1 — red → green → commit
- [ ] 2.25 stored-data: Then it shows an amount of 10.00 — red → green → commit
- [ ] 2.26 stored-data: And version 1 is commit 1, and version 2 is commit 2 — red → green → commit

## 3. What no scenario drives — each arrives with the inner test that needs it

- [ ] 3.1 The migration: `fcon.partition`, `fcon.version`, `fcon.record_block` (by day), `fcon.record_state` (`fillfactor = 50`), `fcon.dataset_progress`, `fcon.snapshot_base`, `fcon.snapshot_block`, `fcon.snapshot_pin`, with the checks, keys and indexes of design § Tables; the store's table descriptions; the test that checks them against the database
- [ ] 3.2 Record-block days: the upgrade makes them from the clock's day through 90 days ahead; readiness is not ready when today's is missing and warns when fewer than 30 remain; the runbook entry
- [ ] 3.3 The store's stamp helper for set-based writes (tenant, actor, the clock's time), refusing SQL that does not scope the tenant, as `tx.execute` does
- [ ] 3.4 Partitions: canonical values, the scheme (value, day, month, bucket), UTC start and end through the time zone (a daylight-saving day is 23 or 25 hours), business names, labels kept, "All"; made once per dataset and values (`insert_if_absent`)
- [ ] 3.5 Fingerprints: canonical JSON, over declared fields when a shape is given; `1` and `1.0`, times, decimals
- [ ] 3.6 Blocks: zstd Parquet with `fcon.format = 1`, `_fcon_deleted`, `_fcon_moved_from`; another format refused; key-list blocks; the reserved marker for encrypted fields
- [ ] 3.7 Reading: an open version is the read lock (a second open read of a partition refused, naming it); each block with the read cursor and a renewed lease; candidates by the read-time look-up; the last copy counts across blocks; a read whose lease expired resumed from its cursor or cleaned up
- [ ] 3.8 Sealing: the sealing lock per partition in partition id order; the comparison again under it; record state written set-based; left-out rows; the counts, records read and unchanged included; deletes over every slice of the read; an empty complete read refused unless allowed; a version with no changes removed, the position still moved; the number in its slice; the commit number last; the dataset position; one audit record per sealed version; the seal's log line, and a warning over 10 s; a changes-only read sealed every 200,000 changes, its position moved with each
- [ ] 3.9 Concurrency: two seals of one partition serialize; seals of two partitions in opposite order do not deadlock; a commit number is never visible before a lower one; a crash (an exception) inside sealing leaves the version open and record state untouched
- [ ] 3.10 Moves: a record read in another slice is a change there only, marked moved from its old slice; the old slice's snapshot drops it from that commit on
- [ ] 3.11 The snapshot: reading a partition as of N from base and tail; compaction builds a base and swaps it whole without the sealing lock; a replaced base kept while a pin needs it; a lost or expired version, or a removed base, fails the read naming it
- [ ] 3.12 Lost versions: a sealed version whose blocks are gone is marked lost (`sealed → lost`); only the transitions of the state machine are allowed
- [ ] 3.13 Tenants: another tenant's dataset, versions and records are never read or written
- [ ] 3.14 The `fcon data` commands' parsing, output and the error helper's messages (an unknown dataset, a line that is not a JSON object, a refused read, an as-of that is no longer kept)
- [ ] 3.15 `pyarrow` added to `fcon-server` with ADR 0021; deptry, the lock file, the container image builds
- [ ] 3.16 Docs: `docs/architecture.md` (the stored data), `docs/runbook.md` (the record-block days warning), `AGENTS.md` § Project's convention 14 names ADR 0022's exception

## 4. Completion

- [ ] 4.1 Run the full suite: every scenario passes, zero pending/undefined steps, HTML report generated
- [ ] 4.2 Every end-of-change check of the Python column passes (ruff, format, pyright strict, vulture, deptry per package, pytest with 100% coverage)
- [ ] 4.3 Run `openspec validate stored-versions --type change` before archive
