# 0012. UUIDv7 ids, made in Python

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #12, point 6

## Context and Problem Statement

Every table needs ids. Sandbox copies and promotion between environments (ADR 0009) must never
collide; ids appear in addresses, so they should not be guessable; and new rows should go at the
end of the key index, as most rows are written once and read by recency.

## Considered Options

- UUIDv7, stored as Postgres `uuid`, made in Python by one helper.
- `bigint` from a sequence.
- Random UUIDs (v4).
- UUIDv7 made by the database (`uuidv7()` in Postgres 18).

## Decision Outcome

Chosen option: "UUIDv7 made in Python", because it is unique everywhere, time-ordered and not
guessable. Measured on Postgres 18 with one million rows: lookups as fast as `bigint`, the key
index about 30% larger, and far smaller than with v4. A row's key is `(tenant_id, id)`. One
helper, `new_id()` (Python 3.14's `uuid.uuid7()`), makes every id, so the id is known before the
row is written and tests can swap in fixed ids. The time inside an id orders rows only; tables
keep their own `created_at`. The dashboard shows the first eight characters; addresses use the
full id; business keys from source systems are separate text columns.

### Consequences

- Good, because rows copied between tenants or environments keep their ids.
- Good, because a test can predict every id it needs.
- Bad, because keys and indexes are larger than with `bigint`.
- Bad, because an id reveals roughly when its row was made.
- Rejected: `bigint`, which collides across sandboxes and environments and is guessable; v4,
  whose random order scatters inserts across the index; ids made by the database, which a test
  cannot fix and code cannot know before the insert.
