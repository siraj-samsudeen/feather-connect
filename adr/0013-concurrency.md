# 0013. Concurrency: row versions, SKIP LOCKED with leases, unique constraints, no transaction across a call

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #12, point 13

## Context and Problem Statement

Several people, agents and workers act on the same rows. Two people editing one row must not
silently overwrite each other; each job must go to one worker, and a dead worker's job must be
picked up again; what must happen once (one delivery per data version and destination, one
answer per repeated API call) must happen once even when two processes try at the same moment.

## Considered Options

- Postgres alone: a row version on every row that changes; work claimed with
  `FOR UPDATE SKIP LOCKED` and an expiring lease; "once" enforced by unique constraints with
  `INSERT … ON CONFLICT DO NOTHING`; default isolation and short transactions.
- Locks held while a person edits (pessimistic locking).
- A separate queue system for jobs.
- Serializable isolation everywhere.

## Decision Outcome

Chosen option: "Postgres alone", because it needs no other system and each rule is checked by
the database itself. Every table whose rows change has `row_version`: an edit applies only if
the row is still at the version that was read, and sets the next one; otherwise nothing changes,
the page says the row was changed by someone else and offers a reload, and the API answers 409.
The store's update helper does this. The worker and durable-execution issues (area 6, D-03) claim
work with `FOR UPDATE SKIP LOCKED` and a lease that expires. Postgres's default isolation, short
transactions, rows locked in a fixed order (tenant, then id), and never a transaction held open
while calling another system: record the intent, commit, call, record the answer.

### Consequences

- Good, because a lost update is impossible through the store, and a duplicate delivery is
  refused by the database.
- Good, because no queue system has to be run, backed up or kept in step with the database.
- Bad, because a person whose edit lost the race must reload and redo it.
- Bad, because a call to another system can succeed while its answer fails to be recorded;
  recovery reads the recorded intent and asks again.
