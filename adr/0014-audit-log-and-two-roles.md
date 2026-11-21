# 0014. The audit log is written by the store, and two database roles make it unchangeable

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #12, points 16 and 17 (catalogue question Q-10)

## Context and Problem Statement

R10.4 asks that every action by a person, an agent or the system leave a record that cannot be
changed, refused actions included, and R7.8 shows it. If each feature writes its own record, one
will forget; if the record can be updated or deleted by the code that writes it, it cannot be
trusted after something went wrong.

## Considered Options

- An append-only table `fcon.audit`, written by the store's update helper in the same
  transaction as the change; a trigger refusing `UPDATE` and `DELETE`; an owner role for
  upgrades and an app role that can only insert and read audit records.
- Database triggers on every table writing the audit record.
- Each feature writing its own record.
- An external log service.

## Decision Outcome

Chosen option: "written by the store, protected by a trigger and two roles", because the change
and its record commit or fail together, and the store already knows who acted, why (a reason in
the context) and in which request. The table holds the tenant, who, what (table and action),
which row, when, and the values before and after; a column marked secret is written as
`(secret changed)`. It is partitioned by month on `created_at`, with the key
`(tenant_id, id, created_at)`, so retention drops whole months (R15.10). The trigger refuses any
`UPDATE` or `DELETE`, whoever asks, so the log is protected even when one user is both roles.
`fcon db upgrade` runs as the owner (`FCON_MIGRATION_DATABASE_URL`, else the app address) and,
when the app address uses a different user, grants it read and write on every `fcon` table and
only read and insert on `fcon.audit`. Creating the two users is a one-time step on the host, in
the deployment guide.

### Consequences

- Good, because no feature can change a row without its record, and no app bug can change a
  record.
- Good, because development and simple installs need one address; the guide recommends two.
- Bad, because a write that bypasses the store's helper leaves no record; the code review checks
  that tables are written through it.
- Bad, because an administrator can still drop a whole month; that is retention, done on purpose.
- Rejected: triggers on every table, which cannot see who acted or why; records written by each
  feature, which one will forget; an external service, one more system and no shared
  transaction with the change.
