## 1. First-time setup — `acceptance-tests/` exists (issue 4); only what this change adds

- [x] 1.1 `support/stack.py` runs `uv run fcon db upgrade` on the run's throwaway database before starting `fcon server`, so the existing scenarios keep a ready product; a helper gives a scenario a throwaway database of its own (new, upgraded, edited, or with an upgrade from a newer version) and a server on a free port pointed at it, dropped at the end
- [x] 1.2 A terminal page object runs `fcon db upgrade` and `fcon db status` against a scenario's database and keeps their output and exit code; a page object reads a started server's log

## 2. Step definitions — one task per pending step; each = fails for the right reason → implement → passes → commit

### Database upgrades

- [x] 2.1 database-upgrades: Given a new, empty database — red → green → commit
- [x] 2.2 database-upgrades: When the operator asks for the database's status — red → green → commit
- [x] 2.3 database-upgrades: Then every upgrade of this version is listed as waiting — red → green → commit
- [x] 2.4 database-upgrades: Given a database that has been upgraded — red → green → commit
- [x] 2.5 database-upgrades: Then every upgrade of this version is listed as applied, with when it ran — red → green → commit
- [x] 2.6 database-upgrades: And none is listed as waiting — red → green → commit
- [x] 2.7 database-upgrades: When the operator upgrades the database — red → green → commit
- [x] 2.8 database-upgrades: Then the operator is told how many upgrades were applied — red → green → commit
- [x] 2.9 database-upgrades: And the database is up to date — red → green → commit
- [x] 2.10 database-upgrades: Then the operator is told the database was already up to date — red → green → commit
- [x] 2.11 database-upgrades: When the operator starts two upgrades of the database at the same time — red → green → commit
- [x] 2.12 database-upgrades: Then both finish without an error — red → green → commit
- [x] 2.13 database-upgrades: But one of its applied upgrades has been edited since it ran — red → green → commit
- [x] 2.14 database-upgrades: Then the upgrade is refused — red → green → commit
- [x] 2.15 database-upgrades: And the operator is told which upgrade changed, and to restore it — red → green → commit

### Logs and health

- [x] 2.16 logs-and-health: Given the product is running on a new, empty database — red → green → commit
- [x] 2.17 logs-and-health: And its log says the database is behind, and how to upgrade it — red → green → commit
- [x] 2.18 logs-and-health: Then the product answers that it is ready to take work, without being restarted — red → green → commit
- [x] 2.19 logs-and-health: Given the product is running on a database that has been upgraded — red → green → commit
- [x] 2.20 logs-and-health: And its log names the upgrade that changed, and says to restore it — red → green → commit
- [x] 2.21 logs-and-health: And the database has one more upgrade, from a newer version — red → green → commit
- [x] 2.22 logs-and-health: Then the product answers that it is ready to take work — red → green → commit

## 3. What no scenario drives — each arrives with the inner test that needs it

- [x] 3.1 The first migration: schema `fcon`; `fcon.migration`, `fcon.tenant` (with `default`, kind, `made_from`, `row_version`, the tenant id check) and `fcon.audit` partitioned by month, key `(tenant_id, id, created_at)`, with the trigger that refuses `UPDATE` and `DELETE`; `pg_c_utf8` on text keys
- [x] 3.2 The runner's rules: name order, late older files applied, checksum of `\n` text, a changed file refused, a newer-version record reported, the advisory lock, `-- fcon: no-transaction`, `fcon.now` from the clock; audit partitions through six months ahead
- [ ] 3.3 Grants after each upgrade: an app user other than the owner gets read and write on every `fcon` table and only read and insert on `fcon.audit` (a test with a second role); `FCON_MIGRATION_DATABASE_URL`, else `FCON_DATABASE_URL`
- [ ] 3.4 The store's helpers: `new_id()`, the clock (system and fixed), the `Context`, `Store.transaction`, `Store.run` with two retries, `tx.execute` / `fetch_one` / `fetch_all` binding the tenant and refusing an unscoped query, `tx.insert` / `tx.update` filling the who-and-when columns and `row_version` and writing the audit record (secret columns as `(secret changed)`, the reason, the request id), the table descriptions checked against the database
- [ ] 3.5 The store's errors: "already exists", "changed by someone else", "busy, try again", and the store's own error for any other; slow statements (over 1 s) logged with their text only
- [ ] 3.6 The pool: `FCON_DATABASE_POOL_SIZE` (5), recycled after 30 minutes, the connection options of point 14, `application_name`, `FCON_DATABASE_PREPARE=off`; opened at server start without waiting for the database
- [x] 3.7 Readiness on its own connection: encoding not UTF-8 (not ready, two-part message), no `und-x-icu` (one warning), behind / ahead / changed with point 9's texts, current audit month missing (not ready), fewer than two months ahead (warning); the watch logs each through the error helper
- [ ] 3.8 The log formatter writes the tenant and request id of the context variable on every line (decision 5)
- [ ] 3.9 The error helper's messages for `fcon db upgrade` and `fcon db status`: database problems, a changed upgrade (exit 2), waiting for another upgrade
- [ ] 3.10 Test fixtures: the session database upgraded once by the runner; a `tenant` fixture with a random `test-<6 hex>` tenant and its context; two for a cross-tenant test
- [ ] 3.11 `scripts/worktree_env.py` runs the upgrade after creating the database
- [ ] 3.12 `scripts/check_migrations.py` (files on `main` unchanged, unique timestamps, the name pattern) and its step in CI's checks job, with `main` fetched
- [ ] 3.13 `.env.example` and `CONTRIBUTING.md`: the new settings and the upgrade step

## 4. Completion

- [ ] 4.1 Run the full suite: every scenario passes, zero pending/undefined steps, HTML report generated
- [ ] 4.2 Every end-of-change check of the Python column passes (ruff, pyright strict, vulture, deptry per package, pytest with 100% coverage)
- [ ] 4.3 Run `openspec validate storage-foundation --type change` before archive
