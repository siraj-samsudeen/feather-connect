# Integration patterns

How one system gets data from another, how Feather Connect does each, and the integration
scenarios the hub supports. For developers writing flows and for anyone deciding whether the hub
fits a need. The numbers (R3.2, UC-04) point to [`requirements.md`](requirements.md); **M1** is
the first release, **M2** the one after it, and **M3** what the design leaves room for, built
after M2.

## How one system gets data from another

| Pattern | How it works | Example | When it fits |
|---|---|---|---|
| **Pull by query** | One system queries the other's database: everything changed since last time | New orders read from a shop's database every 10 minutes | You have database access, and batches are fine |
| **Pull by API** | One system calls the other's web API, usually page by page: list what changed, then fetch each item | Invoices from an accounting service | The other side offers only an API |
| **Push by webhook** | The other system calls you when something happens | A web shop sends "order 1001 created" | Changes are needed within seconds |
| **Change stream (CDC)** | One system reads the other database's own log of changes | A database's logical replication | Near real time from a database, with little load on it |
| **Files** | One side drops a file, the other picks it up | A nightly export to object storage | Large batches, or partners with no API |
| **Request and reply** | One system asks and waits for the answer | "What is the stock of item 42 now?" | A live answer is needed during a user's action |

## How Feather Connect does each

All of them are connectors (R13.3). Whatever way data arrives, it becomes the same thing inside
the hub, a **sealed version** of a slice of a dataset, and **one delivery logic** takes every
version to every destination, with the same order, retries, exactly-once effect, holds and
history.

| Pattern | In the hub | M |
|---|---|---|
| Pull by query | A flow on a schedule; change found by a change stamp with a look-back, by comparing whole slices (which also finds deletes), or by reloading (R3.2) | M1 |
| Pull by API | The same, through a shared web client with retries, call budgets and secrets kept out of logs (R13.10, R6.5) | M1 |
| Push by webhook | Stored at once and acknowledged within 200 ms (Q-18); the event either carries the record or names it, and the hub fetches the latest copy from the source | M1 |
| Change stream (CDC) | One more source of events, resumed from where it stopped (R3.15) | M2 |
| Event bus (publish and subscribe) | The hub subscribes and resumes from its replay position, reporting a gap when the bus no longer holds the events (R3.28); other systems subscribe to the hub's own events (R3.29) | M2 |
| Files | Object storage connector (UC-05); large files and documents in object storage (R3.16, R3.27) | M1, large files M2 |
| Request and reply | Other systems ask the hub for its data (R3.23), or the hub stands between two systems (R3.24) | M2 |
| Event formats and contracts | Events in the CloudEvents format (R3.30); versioned shapes for the events the hub publishes (R3.31); statuses that arrive over time (R3.32); request and reply over events (R3.33) | M3 |

## Integration scenarios with the hub

### Moving data from systems to systems

| Scenario | What happens | Example | Covered by | M |
|---|---|---|---|---|
| **One source, many destinations** | One dataset read once, delivered to every destination, each moving, failing and recovering on its own | Orders to the warehouse, the accounts service and a reporting database | UC-03, R3.1, R6.10 | M1 |
| **Many sources, one destination** | Several flows deliver into one place | Orders from three shops into one warehouse | One flow per source, R3.1 | M1 |
| **Batch load** | A table or an API read on a schedule into a warehouse | A database table to the warehouse every night | UC-01, UC-02 | M1 |
| **Near real time** | A webhook arrives and a destination is updated within seconds | A web order into the order system | UC-04, Q-01 | M1 |
| **Event as a trigger** | The webhook only names the record; the hub fetches the latest copy, so the order of events doesn't matter | "Order 1001 changed" → fetch order 1001 | R3.2, data-model point 12 | M1 |
| **Differences only** | A query compared with last time, and only what changed is pushed | Today's prices to a sales channel | UC-06 (its template R1.8 is M2) | M1 |
| **History, then live** | A new destination first receives the current state of every slice, then follows live | A new reporting database added to a running flow | UC-09, R3.11, HC-11 | M1 |
| **Backfill** | A range of past slices read again, previewed first, within call budgets | Last year's orders reloaded after a fix | UC-08, R5.4, R8.8 | M1 |

### Shaping and checking data on the way

| Scenario | What happens | Example | Covered by | M |
|---|---|---|---|---|
| **Transform per destination** | Each destination can change, leave out or split records, or run SQL on a batch | Totals in the warehouse, line items to the accounts service | R4.1, R4.2 | M1 |
| **Enrich with a lookup** | A record looks up another dataset's latest state, one state for a whole delivery | An order gets the customer's region | R4.3, HC-18 | M1 |
| **Derived datasets** | A dataset that is a query over others, recomputed on a schedule | A price that takes effect on a date | R4.4, HC-20 | M1 |
| **Validation** | Records checked against a declared shape; bad ones set aside with the reason, the rest go on | An order with no customer is set aside | R4.5, R6.10 | M1 |
| **Shape changes** | An added field passes; a dropped field or changed type waits for a person | The source drops a column | R3.14, HC-12 | M1 |

### Writing into business systems

| Scenario | What happens | Example | Covered by | M |
|---|---|---|---|---|
| **Business operations** | A destination performs an action, safe to repeat and able to reverse | Post an invoice; reverse it on request | UC-07, R6.6, R6.11, HC-09 | M1 |
| **Keep each system's own id** | The id a destination gave a record is kept, so later changes update the same record | Order 1001 is `SO-77` in the ERP | R3.25 | M1 |
| **Parent before child** | A destination waits until the related record has arrived | An order before its lines; a customer before their orders | R3.26 | M1 |
| **Approval in the middle** | A route, an environment or particular records need a person's approval; the rest go on | Payments above a limit wait for approval | R6.7, R8.3 | M1 |

### Timing and coordination

| Scenario | What happens | Example | Covered by | M |
|---|---|---|---|---|
| **On a schedule** | A calendar schedule with a time zone, or an interval down to seconds | Every 10 minutes, Kolkata time | R5.1 | M1 |
| **When data is complete** | A flow starts once the data it needs is ready, per period, per shop | The daily report once yesterday's orders and lines are in | R3.13, R3.19 | M1 |
| **Opening hours** | A system is read or written only in the hours it allows; work waits visibly | An ERP open to writes 06:00–22:00 | R5.6, HC-21 | M1 |
| **Shared call limits** | Several flows share a system's call limit, with a share reserved for urgent work | One daily API limit for all flows | R6.5, HC-07 | M1 |
| **Business calendars** | Working days and public holidays | First working day of the month | R5.13 | M2 |

### Other systems asking the hub

| Scenario | What happens | Example | Covered by | M |
|---|---|---|---|---|
| **The hub writes where they read** | A destination they read on their own: a database table, files | A table a reporting tool queries | Any route | M1 |
| **Subscribe to the hub** | A system registers itself for the hub's events and receives them as they happen | A billing system told whenever an order is delivered | R3.29 | M2 |
| **Data API** | A system asks the hub for the latest record, or for changes since its last call | A mobile app gets a customer's current record | R3.23 | M2 |
| **Middleman** | A system asks the hub; the hub calls the system that holds the data and answers in the shape asked for | "Stock of item 42", answered from the warehouse system | R3.24 | M2 |

### Running across boundaries

| Scenario | What happens | Example | Covered by | M |
|---|---|---|---|---|
| **Systems inside a private network** | A small program inside the network connects out to the hub and reads or writes there for it | A database with no access from outside | R13.7 | M2 |
| **Several business units** | Tenants kept apart, each with its own connections, users and budgets | Two companies of one group | R14.1–R14.3 | M1 (one tenant) / M2 |
| **Erasing a person's data** | A person's data erased from every copy the hub keeps | A customer asks to be forgotten | R10.16 | M2, by early 2027 |

## Choosing a pattern

- **A destination that can receive:** let the hub push to it. That is where every guarantee lives:
  order, retries, exactly once, holds and history.
- **A source that can send webhooks:** use them for speed, and add a scheduled full comparison
  to catch what the webhooks missed (R3.3).
- **A webhook that carries only an id:** use it as a trigger to fetch the latest record.
- **A write that must never be lost:** send it as a webhook, stored at once and delivered
  reliably, rather than through a middleman call that only lasts while the caller waits.
- **A live answer during a user's action:** a middleman endpoint (R3.24), or the data API
  (R3.23) when the hub's stored copy is fresh enough.
