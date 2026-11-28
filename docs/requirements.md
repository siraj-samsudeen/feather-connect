# Feather Connect — requirements catalogue

What the product must do, for whom, and in which milestone. It is the source that feature issues are
filed from (issue #2). It holds no specs and no design: the spec of a capability is written by the
OpenSpec change that builds it, and a technology choice is made by the change that needs it (§11).

- **Status:** draft for the owner's review, 17-Nov-2026 (second pass: 36 requirements, a quality target and two decisions added; third pass: 4 requirements; fourth pass, from a full inventory of what was built: 21 requirements and 12 widened; fifth pass: 1 requirement and 1 widened).
- **Milestones:** **M1** is the first release. **M2** is everything after it. Each requirement names one.
- **Numbers:** `G` goals, `P` people, `UC` use cases, `R` requirements (`R3.2` is the second of area 3),
  `HC` hard cases, `Q` quality targets, `D` decisions to make. A number is never reused.

## 1. Summary

Feather Connect is an open-source (MIT) integration hub. It moves data from one source to many
destinations, in batches and as events arrive, with one data model and one dashboard.

A flow is ordinary Python code. Developers and AI assistants write, review and test it like any
other code. Operators and AI agents watch every flow and act on it from one dashboard, an API and
a command line: read a business slice again, send history to a new destination, approve a posting,
pause a destination. It runs on a laptop with one command and needs one database in production.

It is a general-purpose product. Nothing in it is built for one organisation, vendor or industry.

## 2. The problem

- **Integration work is split across tool families that each solve one part.** Connector-rich
  commercial platforms are closed, costly and weak at replaying history. Batch loaders move tables
  but not application events. Streaming stacks are heavy to run. Durable-workflow engines make code
  reliable but have no data model or connectors. Batch orchestrators don't handle low-latency events.
- **Teams stitch several of these together with scripts.** Monitoring is scattered, and recovery
  means commands and SQL written by the few people who built the pipelines.
- **Work can't be addressed by business slice.** Tools think in rows and cursors, so "read one
  shop's sales for one day again" can't be asked for.
- **Reading and writing are coupled.** If a destination is down while a source can be read, the
  read is lost.
- **Awkward sources are common.** Tables with no change stamp, rows deleted for good, a key
  rewritten in place, rows that become visible late, rows back-dated into a closed period.
- **Vendor call limits are uncoordinated.** One cap is shared by every reader and writer of a
  system, and nothing shares it out.
- **Visual low-code flows are hard to diff, review and test,** and hard for AI to generate
  reliably.

## 3. Goals

| ID | Goal | Met when |
|---|---|---|
| G1 | One model for batch loads and application events | A scheduled extract, a webhook event and an API posting are all built from the same few concepts |
| G2 | Flows are code that developers and AI can write, review and test | On a fixed set of tasks, at least 80% of AI-written flows pass validation and their tests with no fix by hand |
| G3 | One dashboard to watch **and act** | An operator recovers a failed delivery, reads a slice again and replays history without a command line or SQL |
| G4 | Easy to run and keep running | A working demo is on screen within 5 minutes of a clean install; production needs one database |
| G5 | Safe across environments | Development, test and production run the same build with their own settings; a protected environment asks for a reason for every change and a second person for what can't be undone |
| G6 | Batteries included | The first release ships general-purpose connectors and flow templates (areas 13 and 1) |
| G7 | AI can operate the hub safely | An agent with a read-only token finds out why a delivery failed and can change nothing (M1); with more rights it asks, and a person approves (M2) |

**Not goals:** a visual flow designer; sub-second, very high-volume streaming; a hosted service; a
replacement for a data warehouse or reporting tools; API management; general business-process
management beyond approvals.

## 4. People

| ID | Who | Needs | Uses |
|---|---|---|---|
| P1 | Integration developer: writes and reviews flows and connectors, often with an AI assistant | A fast local loop, simulated sources, clear errors, tests, templates | Code, command line, dashboard |
| P2 | Operator: support and operations staff, juniors included | A clear picture of health, safe recovery in a few clicks, settings without code | Dashboard |
| P3 | Administrator: installs and upgrades environments | Simple deployment, users, secrets, call budgets, upgrades | Command line, dashboard |
| P4 | AI agent | Typed code interfaces, machine-readable command output, tools with clear rights | Code, command line, agent tools |
| P5 | Business owner of a process | Freshness, readiness, approval requests, alerts | Dashboard, alerts |
| P6 | Open-source contributor | A connector kit, a conformance check, a contribution guide | Code, repository |

## 5. Terms

| Term | Meaning |
|---|---|
| Connector | Code that reads from or writes to one kind of system |
| Connection | A connector set up for one environment, with its address and secrets |
| Dataset | A named stream of keyed records from one source |
| Record | One keyed item, such as an order with its lines. Its key is its business identity |
| Partition | A named business slice of a dataset, such as one shop on one day, with an explicit time zone. The unit that is planned, read again, checked and backfilled |
| Version | What one read of a partition produced: records added, changed and deleted. Sealed once and never changed. A *complete* version describes the whole slice |
| Change strategy | How a dataset finds what changed: by a change stamp, by comparing a whole slice with the last one, by reloading the slice, or by events pushed to it |
| Spool | Where versions wait, durably, until every destination has taken them |
| Route | One destination of a dataset: an optional transform, a sink, and how it writes |
| Delivery | One version on one route. The list of deliveries, the ledger, is each route's progress and its failures |
| Flow | The unit that is deployed: what it reads, where it delivers, and when it runs |
| Run / task | One execution of a flow, and the durable steps inside it |
| Readiness | "Complete through this point" for a dataset or a group of datasets |
| Budget | A shared limit on calls to a system, over one or more time windows, with a reserved share |
| Hold | Work waiting for a person's decision |
| Package | A versioned bundle of flows, installed into an environment and switched on flow by flow |
| Environment | One deployment: development, test or production. A *protected* one has extra safeguards |
| Tenant | A namespace for data, settings, users and budgets inside an environment |

## 6. Use cases

| ID | Use case | Example | Who | Milestone |
|---|---|---|---|---|
| UC-01 | Copy a database table to a warehouse, only what changed | An orders table to an analytics database | P1 | M1 |
| UC-02 | Pull a web API into a warehouse within a shared daily call limit | Invoices, list then detail, from an accounting service | P1, P2 | M1 |
| UC-03 | Send one source to many destinations | A price list to three sales channels | P1 | M1 |
| UC-04 | Receive webhooks and update an API within seconds | A new web order to an order system | P1 | M1 |
| UC-05 | Load files dropped in object storage | CSV or Parquet files to a database | P1 | M1 |
| UC-06 | Compare a warehouse query with last time and push only the differences | Today's effective price to a sales channel | P1 | M1 |
| UC-07 | Post business documents with approval and a way to reverse | A day's sales of one shop to a ledger | P1, P5 | M1 |
| UC-08 | Read a business slice again, or backfill a range, from the dashboard | One shop, one day | P2 | M1 |
| UC-09 | Replay history to a destination added later | A fourth sales channel | P2 | M1 |
| UC-10 | Find out why a delivery failed and fix it; follow one record by its key | "Where is invoice 1001?" | P2, P4 | M1 |
| UC-11 | Write a flow with AI, validate it, run it on simulated data, promote it | A new supplier feed | P1, P4 | M1 |
| UC-12 | An agent investigates with read-only rights | An agent explains last night's failures | P4 | M1 |
| UC-13 | Move a flow from development through test to production | Version 1.4 of the price flow | P1, P3 | M1 |
| UC-14 | Simulate a source for demos and testing, with faults on purpose | Duplicates, late rows, refused and slow calls | P1 | M1 |
| UC-15 | An agent acts within its rights, and asks in production | An agent asks for a retry; a person approves | P4 | M2 |
| UC-16 | Follow changes in a database as they are committed | New rows reach a destination in seconds, no polling | P1 | M2 |
| UC-17 | Reach a system that can only be called from inside a private network | A database behind a firewall | P1, P3 | M2 |
| UC-18 | Serve several tenants from one environment, kept apart | Two business units, each with its own connections and users | P3 | M2 |

## 7. Requirements

In the order a person meets them. **M** is the milestone.

### Area 1 — Writing a flow

| ID | Requirement | M |
|---|---|---|
| R1.1 | A flow is Python code. There is no proprietary language, markup or visual format. | M1 |
| R1.2 | A dataset is declared by its source, its key, how it is partitioned, how change is found, and optionally its shape. Behaviour beyond the defaults is added in code, not through a growing list of switches. | M1 |
| R1.3 | A command starts a new flow or a new connector with code, settings and tests, optionally from a template. | M1 |
| R1.4 | A flow runs once on the developer's machine, in one process, against in-memory or simulated systems. | M1 |
| R1.5 | A command checks a project without running it (references, budgets, partitions, shapes, settings, names shared by two flows, cycles among derived datasets or waiting flows) and answers in a form a program can read. Warnings do not fail it. | M1 |
| R1.6 | A test kit lets a flow's tests load source records, run the flow, and check what each destination received, the ledger and the holds. | M1 |
| R1.7 | Templates for common flows can be copied into a project and then edited freely: table to warehouse, API to warehouse, files to database, webhook to API, and a fan-out demo. | M1 |
| R1.8 | A template for comparing a warehouse query and pushing the differences. | M2 |
| R1.9 | Settings are layered: defaults in code, then the project, then the environment. The dashboard shows each value in force and which layer set it. | M1 |
| R1.10 | A validation error says what is wrong and how to fix it. | M1 |

### Area 2 — Packaging and deploying

| ID | Requirement | M |
|---|---|---|
| R2.1 | Flows are deployed as a versioned package, built in the team's own repository. Packages are the only way to deploy. | M1 |
| R2.2 | The server has a package registry built in. A team's own package index can be added beside it. | M1 |
| R2.3 | Installing checks the package and stores it. Its flows start switched off. | M1 |
| R2.4 | Each flow is switched on and off per environment. Runs in progress finish. Switching on another version replaces the current one, and going back works the same way. | M1 |
| R2.5 | Installing, upgrading, going back and switching off need no restart, and other packages keep running with no run lost or doubled. | M1 |
| R2.6 | Every name a package brings carries the package's name, so two packages can't clash. | M1 |
| R2.7 | A package is promoted from one environment to the next by its checksum, so what was tested is what runs. Each environment shows which version of the code every flow runs. | M1 |
| R2.8 | A package can be signed, and an environment can refuse unsigned ones. A version installed before signing was required is checked again when it is switched on. | M1 |
| R2.9 | A flow's schedule can be changed, and the flow switched off, per environment without a new package version. | M1 |
| R2.10 | A command shows how flows and settings differ between two environments before promoting. | M2 |
| R2.11 | A package records the exact versions of everything it depends on, so an install runs what was tested. Each package runs in an environment of its own, so two packages can need different versions of a library. | M1 |
| R2.12 | A token can be limited to publishing: it can add a new version and nothing else. A published version is never replaced; it can be withdrawn. | M1 |
| R2.13 | A version is checked by loading it in isolation before it can be switched on; one that fails the check can't be. | M1 |
| R2.14 | A package can be installed from a file, behind the same checks, where the registry can't be reached. | M1 |
| R2.15 | A version can be uninstalled only when none of its flows is switched on. Its history stays. | M1 |
| R2.16 | Installing checks a package's size, checksum, description, product compatibility and pinned dependencies, and names the check that failed. Without a version, the newest one not withdrawn is installed; trial versions only when asked for. | M1 |
| R2.17 | A package's code runs with no access to the server's secrets, users, tokens or audit log, nor to another package's secrets. A package that hangs or floods its output while being checked is stopped. | M1 |
| R2.18 | A package that keeps failing to start is shown as failing and restarted after a pause; the version before it keeps serving meanwhile. | M1 |
| R2.19 | A run finishes on the code it started on, whatever version is switched on meanwhile. | M1 |
| R2.20 | A flow that waits on another package's data can be switched on only once the flow producing that data is on; the refusal names it. | M1 |
| R2.21 | Going back is possible only to a version that has served before. | M1 |

### Area 3 — Moving data

| ID | Requirement | M |
|---|---|---|
| R3.1 | One dataset is delivered to any number of routes. Each route moves on, fails and recovers on its own. | M1 |
| R3.2 | Change is found by a change stamp with a look-back; by comparing a whole slice with the previous one, which also finds rows deleted for good; by reloading the slice; or by events pushed in. A custom strategy can be written in code. | M1 |
| R3.3 | A dataset read by change stamp can also be compared in full on a schedule, to catch what the stamp missed. | M1 |
| R3.4 | Partitions name business slices with an explicit time zone. They are the unit of planning, reading again, checking and backfilling. | M1 |
| R3.5 | Each read produces a version that is never changed afterwards. Versions are kept for a set time. | M1 |
| R3.6 | Reading never waits for a destination. What was read is stored durably first, so a destination being down can't lose a read. | M1 |
| R3.7 | A route applies the versions of a partition in order. Pushed datasets keep the order per key. Optionally a newer whole document replaces an older one that failed. | M1 |
| R3.8 | A record that hasn't changed since it was last seen is not delivered again. | M1 |
| R3.9 | A complete read that returns nothing fails unless the dataset allows an empty slice, so an empty answer can't wipe a destination. | M1 |
| R3.10 | A record that moves from one slice to another is an update. It leaves no stale copy and is not deleted and re-created. | M1 |
| R3.11 | Any version still kept can be replayed to a route. Replaying an older version while a newer one exists is refused, naming the newer one. A route added to a live flow first receives the latest state of each slice, then follows live. | M1 |
| R3.12 | A route writes by updating by key, by appending with history, by replacing a whole slice at once, or as a business operation (R6.6). | M1 |
| R3.13 | Readiness is tracked per dataset and per group of datasets. It can start a flow or make it wait, once per period, and never holds up routes that didn't ask. Data arriving after a period closed is run again, warned about or ignored, as the flow says. | M1 |
| R3.14 | When a dataset's shape changes, added fields pass; dropped fields and changed types wait for a person. The rule can be stricter or looser per dataset or route. | M1 |
| R3.15 | Changes committed to a database are followed as events. M1's event model is designed to take them (D-04). | M2 |
| R3.16 | Very large reads and long archives can be spooled to object storage instead of the database. | M2 |
| R3.17 | A sink that accepts work and confirms each record later is supported; records it turns down then are set aside like any other. | M2 |
| R3.18 | Partitions can be by day or month in a time zone, by fields, by a combination, or by a hash that spreads keys while keeping each key's order. A custom scheme can be written in code. | M1 |
| R3.19 | Readiness distinguishes *read* through a point from *delivered to a named route* through it. It can be split by a field, so each value (each shop) is ready and starts its flow on its own. A source can say a period is closed. A flow can ask not to be started more often than a set interval. | M1 |
| R3.20 | A long read that is interrupted resumes from where it had got to. | M1 |
| R3.21 | When a run reads several slices in full, deletes are decided only after all of them are read. | M1 |
| R3.22 | When one read holds two copies of a record, the last one counts. | M1 |
| R3.23 | Another system can ask for a dataset's data on demand, read-only: the latest record by its key, and the records changed since a point it got earlier, so it can catch up from where it left off. Each answer says which version and time it comes from. The same rights, tenant checks, masking of personal data, rate limits and audit apply as everywhere else. Each such caller is a route of its own whose destination collects the data: the ledger knows what it has collected, data it hasn't collected yet is kept for it, and the dashboard shows when it falls behind. A caller that falls behind past the keeping time is told so and starts again from the current state. Its token sees only the datasets it is given. | M2 |
| R3.24 | The hub can stand between two systems as a middleman. A flow package declares an endpoint: what it accepts, what it answers, and the code that calls the other system and transforms the answer, so the caller never needs to know that system. The caller waits for the answer within a set time limit, or gets a clear failure. A write through an endpoint takes the caller's idempotency key, so a retry takes effect once. An endpoint may answer from a dataset's stored copy instead of calling the other system. It uses the same connectors, call budgets, rights, tenant checks, masking and audit as everything else. Writes that must never be lost are better sent as webhooks, which are stored at once and delivered reliably. | M2 |
| R3.25 | The hub keeps, for each route, the id a destination gave each record, against the record's key, so a later change updates that same record there instead of creating another. Ids come from the destination's answers. They can be looked up and corrected by an operator, and are kept while the dataset exists. | M1 |
| R3.26 | A route can wait until a related record has reached the same destination: an order's lines after the order, a customer before their orders. The route names the related dataset and the key that links them; a record whose parent hasn't arrived waits, visibly, and goes once it has. Routes that don't ask are never held up. | M1 |
| R3.27 | Documents and other large files attached to records, such as invoices' PDFs, pass through the hub, kept in object storage (R3.16). | M2 |
| R3.28 | A dataset can subscribe to an event bus or a change stream (a business application's events, a message broker, a database's change log): it holds the connection, takes events in order, and resumes from its replay position after a restart. When the bus no longer holds the events since that position, the gap is reported and the scheduled full comparison (R3.3) catches up. | M2 |
| R3.29 | Another system can subscribe itself to the hub's events (a record delivered, a record changed in a dataset), naming where to send them and which datasets and kinds of event; each subscription is a route of its own, with the same guarantees, keeping times and history, and its token sees only the datasets it is given. | M2 |

### Area 4 — Transforming

| ID | Requirement | M |
|---|---|---|
| R4.1 | Each route can change, leave out or split records one at a time, or change a batch at a time as a table. | M1 |
| R4.2 | A batch can be transformed with a SQL query. | M1 |
| R4.3 | A transform can look up another dataset's latest state. One delivery uses one state of it throughout, and records which. | M1 |
| R4.4 | A dataset can be a query over other datasets, recomputed on a schedule, so a change that takes effect on a date is delivered on that date. | M1 |
| R4.5 | Records are checked against a declared shape. Invalid ones are set aside with the reason while the rest go on; a flow can ask for the whole version to fail instead. | M1 |
| R4.6 | A dataset that is a query over others can itself be partitioned. | M2 |
| R4.7 | A query can read only the batch and the datasets it names, never files or web addresses. | M1 |

### Area 5 — Starting and scheduling

| ID | Requirement | M |
|---|---|---|
| R5.1 | A flow starts on a calendar schedule with a time zone, at a fixed interval down to seconds, or by hand from the dashboard, the command line or the API. | M1 |
| R5.2 | A flow starts when a webhook arrives. | M1 |
| R5.3 | A flow starts when the data it needs is ready (R3.13). | M1 |
| R5.4 | A backfill over a range of partitions is previewed before it runs, and runs within limits on parallel work and call budgets. | M1 |
| R5.5 | A flow or a single route can be paused and resumed. | M1 |
| R5.6 | A connection can declare the hours it may be read or written. Work outside them waits, visibly, and runs when the hours open. | M1 |
| R5.7 | A flow starts on database change events (R3.15). | M2 |
| R5.8 | When a flow is due while its last run is still going, it queues, skips or cancels the earlier run, as the flow says. | M1 |
| R5.9 | After downtime, the missed starts are caught up as one run or one by one, as the flow says. | M1 |
| R5.10 | A flow that polls every few seconds shows as one run a day, with each poll inside it, so the list of runs stays readable. | M1 |
| R5.11 | With several servers running, exactly one schedules. | M1 |
| R5.12 | A pause can be given an end, after which it lifts by itself. | M1 |
| R5.13 | Schedules and readiness can follow a business calendar: working days and public holidays, per environment. | M2 |

### Area 6 — Reliability

| ID | Requirement | M |
|---|---|---|
| R6.1 | Killing any process loses no work that was acknowledged. | M1 |
| R6.2 | Failed calls are retried with growing, randomised waits that honour what the other system asks for. Steps have time limits. | M1 |
| R6.3 | Each version takes effect on each route once, even if a process dies between writing and recording it. | M1 |
| R6.4 | Nothing fails silently. Every scheduled start and every delivery is recorded, skipped ones too, with the reason. | M1 |
| R6.5 | Call budgets are named and shared across flows and routes, with several windows at once (per second up to per day) and a share reserved for high-priority work. Reaching a limit is a visible wait, not a failure. | M1 |
| R6.6 | A route that performs business operations must be safe to repeat and able to reverse what it did. An operator can reverse a delivery. | M1 |
| R6.7 | A route can require approval always, per environment, or per record. Records that need it wait; the rest go on. | M1 |
| R6.8 | By default one writer works on a route's partition at a time; parallel work is configurable. | M1 |
| R6.9 | After a database restore, versions whose stored data is gone are marked lost, not silently skipped. | M1 |
| R6.10 | A problem with one record sets that record aside. A problem with a whole version (a refused sign-in, a missing destination) fails or holds that delivery, which stops only its own partition on its own route. | M1 |
| R6.11 | A business operation interrupted part-way resumes without repeating the part already done. | M1 |
| R6.12 | A read that could never fit within its budget fails at once, naming the budget, instead of waiting for ever. | M1 |
| R6.13 | One flow failing never stops other flows from starting. | M1 |

### Area 7 — Dashboard: watching

| ID | Requirement | M |
|---|---|---|
| R7.1 | An overview shows failures, stale datasets, budget use, workers, waiting holds and alerts. | M1 |
| R7.2 | A list of flows and a page per flow: a picture from sources through routes to destinations, the settings in force and where each came from, and the code version. | M1 |
| R7.3 | A grid shows every dataset, partition and route over time, and opens into detail. | M1 |
| R7.4 | Runs and their tasks: timeline, inputs, logs, attempts, and the records each task read or wrote. A planning task that succeeded at its first try is shown as one line; one that failed or was retried keeps its row, with why. | M1 |
| R7.5 | The delivery ledger, and failures grouped by error. | M1 |
| R7.6 | One record followed by its business key across versions and routes; two versions compared; sample values masked. | M1 |
| R7.7 | Pages for records set aside, holds, budgets, readiness, connections, secrets (never shown once set), packages and registries, users, and search. | M1 |
| R7.8 | The audit log, filtered by who, what and which item. | M1 |
| R7.9 | Every view has an address that can be shared; filters are part of it. | M1 |
| R7.10 | Pages that only show information work with JavaScript off. | M1 |
| R7.11 | Light and dark themes, and a keyboard command menu. | M1 |
| R7.12 | Views of freshness against a target and of unusual volumes. | M2 |
| R7.13 | One page summarising several environments, each opening its own dashboard. | M2 |
| R7.14 | The workers connected, the code version each runs, and when each was last heard from. | M1 |
| R7.15 | A task's log and the dashboard's charts come from the product's own stored data; no separate logging or metrics system is needed. | M1 |
| R7.16 | A partition is shown in business words ("Shop 12 · 18 Oct"), not as a key string. | M1 |
| R7.17 | A run that delivered nothing says why: nothing had changed, or the flow was paused, or it was waiting. | M1 |
| R7.18 | Every page shows which environment it is, who is signed in with which role, and whether the server, the database and the workers are well, with the product's version. | M1 |
| R7.19 | A delivery shows each attempt, and what the destination answered for each record, with secrets removed. | M1 |
| R7.20 | A flow found running on two versions of the code at once is flagged. | M1 |
| R7.21 | A run's whole log on one page: every task's lines in the order they were written, each naming its task, partition and route and linking to that task's own log. It can be narrowed to warnings and errors, and is paged. | M1 |
| R7.22 | Pages that work on a narrow screen, such as a phone's. Operators use the dashboard on laptops and desktops, so it is built for those first (owner, 21-Nov-2026). | M2 |

### Area 8 — Dashboard: acting

| ID | Requirement | M |
|---|---|---|
| R8.1 | Run now, read partitions again, backfill, cancel. | M1 |
| R8.2 | Retry, skip, set aside and replay deliveries, one or many, with a preview of the effect first. | M1 |
| R8.3 | Approve or reject a hold, with a reason. | M1 |
| R8.4 | Close a partition by hand, and start a readiness-triggered flow now. | M1 |
| R8.5 | Test a connection. View and edit a connection's settings; replace or remove a secret. Every change is audited with the old and new value, secrets excepted. | M1 |
| R8.6 | Everything the dashboard can do, the API and the command line can do, under the same rights and the same audit. | M1 |
| R8.7 | Budgets, parallel work and connection hours can be changed while running, each with a reason and an optional end time; the difference from the deployed settings is shown. | M2 |
| R8.8 | A mass action is two steps: a preview that says what it will touch and what budget it is expected to use, then a confirmation that is valid for a short time and only for exactly what was previewed. A selection must be small enough to review. | M1 |
| R8.9 | The API is described in a standard, machine-readable form. A repeated call with the same key takes effect once. Errors come in one standard shape, and long lists are paged. | M1 |
| R8.10 | Every result of an action links to its audit record. | M1 |
| R8.11 | A slice can be checked against its source: read again and compared with the last read, changing nothing. | M1 |
| R8.12 | A record or an incoming event set aside can be sent again once its cause is fixed, or dismissed with a reason. | M1 |
| R8.13 | Flows can be run, paused and resumed, and runs cancelled, several at a time, up to a hundred. | M1 |

### Area 9 — Environments

| ID | Requirement | M |
|---|---|---|
| R9.1 | Development, test and production are separate deployments of the same build, each with its own database, connections, secrets and settings. | M1 |
| R9.2 | In a protected environment every change needs a reason, mass actions need a preview and a confirmation, and actions that can't be undone wait for a second person. New tokens there are read-only unless more is asked for. | M1 |
| R9.3 | Development and test environments can run on simulated systems. | M1 |
| R9.4 | Several test environments can share one machine, each with its own database. | M1 |
| R9.5 | A test environment can be refreshed from production with personal data masked. | M2 |

### Area 10 — Security

| ID | Requirement | M |
|---|---|---|
| R10.1 | Local users and API tokens. An administrator adds users, resets passwords, disables leavers, and makes, lists and revokes tokens. A password set by an administrator works for one sign-in; each user then chooses their own. | M1 |
| R10.2 | Roles: viewer, operator, developer and administrator, plus two grants: deciding holds, and seeing personal data unmasked. | M1 |
| R10.3 | Secrets are referenced, never shown. They come from environment variables, files, or the database, encrypted with a key kept outside it. They are never logged or sent to a browser. | M1 |
| R10.4 | Every action by a person, an agent or the system leaves a record that can't be changed, and so does every action that was refused. | M1 |
| R10.5 | Fields marked as personal data are masked on the dashboard, the API and the command line. Unmasking needs the grant and is recorded. | M1 |
| R10.6 | Webhooks are checked by signature, with protection against replays, a size limit and a rate limit per source. A package declares its webhooks; it does not bring its own receiver. | M1 |
| R10.7 | The dashboard uses a secure session, a token on every form against forged requests, and a policy that refuses inline scripts. | M1 |
| R10.8 | Sign-in through an organisation's identity provider. | M2 |
| R10.9 | Secrets can be read from secret-management services. | M2 |
| R10.10 | Error text from other systems is cleaned of secrets before it is stored or shown. | M1 |
| R10.11 | Tokens can expire, and each is limited to a role. | M1 |
| R10.12 | Repeated failed sign-ins are slowed, by user and by address. Signing out, or a new password, ends every session of that user. | M1 |
| R10.13 | There is always an administrator: the last one cannot lose the role. A token never acts above its user: when a user is demoted, disabled or removed, their tokens follow at once. | M1 |
| R10.14 | The key that encrypts stored secrets can be changed; every secret is then sealed again under the new key. | M1 |
| R10.15 | Building a package warns when a secret is written out in plain instead of being named. | M1 |
| R10.16 | A person's data can be erased on request from every copy the hub keeps, and from what a destination holds when its route can delete. Fields marked as personal data are encrypted with a key for each person, and erasing destroys that key, so no sealed version is rewritten. Each erasure is recorded without the data, and applied again after a restore. Planned no later than early 2027, ahead of India's data protection duties (owner, 28-Nov-2026). | M2 |

### Area 11 — Alerts and visibility

| ID | Requirement | M |
|---|---|---|
| R11.1 | Logs are structured and carry the ids of the flow, run, task, dataset, partition, version and route. | M1 |
| R11.2 | Alert rules: a run failed, a delivery failed, a budget is nearly used up, a hold is waiting, a scheduled start was skipped, a dataset is stale, a dataset has gone quiet, no worker is alive. Rules are set per environment. | M1 |
| R11.3 | Alerts go to a webhook, team chat or email. Each channel can be sent a test alert. Alerts are not repeated, a notice that fails to send is tried again, and alerts can be acknowledged and snoozed. | M1 |
| R11.4 | Health and readiness addresses that an outside monitor can check. | M1 |
| R11.5 | Metrics and traces can be exported in standard formats. The dashboard works without them. | M2 |
| R11.6 | Alert rules for a partition that was expected by a time and hasn't arrived, and for volumes far from what is usual. | M2 |

### Area 12 — Working with AI

| ID | Requirement | M |
|---|---|---|
| R12.1 | A new project carries instructions for AI assistants; every command can answer in a form a program can read; an agent can ask what a connector can do. | M1 |
| R12.2 | Agent tools that read, and local authoring tools that change nothing, for a read-only token, under the same rights and audit as a person. | M1 |
| R12.3 | A ready-made procedure for an agent to investigate a failed delivery. | M1 |
| R12.4 | A fixed set of flow-writing tasks with hidden tests, to measure goal G2. | M1 |
| R12.5 | Agent tools that act, under the same rights and audit as a person. | M2 |
| R12.6 | In a protected environment an agent may only ask; what it asks for waits for a person. | M2 |
| R12.7 | An assistant inside the dashboard. | M2 |
| R12.8 | Data handed to an agent is masked like any other, even when the agent's user may see it unmasked, and marked as untrusted content. Secrets are never handed over. Lists are capped, and each token has its own rate limit. | M1 |
| R12.9 | Agent tools that start a flow or a connector from a template and run it locally, and ready-made procedures for writing a new flow and a new connector. | M2 |

### Area 13 — Connectors

| ID | Requirement | M |
|---|---|---|
| R13.1 | A connector kit: how to read, how to write, what the connector can do, its settings, a self-check and a way to list what it offers. | M1 |
| R13.2 | A connector says what a call and a record cost against a budget, so previews estimate budget use. | M1 |
| R13.3 | General-purpose connectors: in-memory, a simulator, a relational database, object storage, web APIs (REST and GraphQL), webhooks, plain HTTP calls, and an embedded analytics database. | M1 |
| R13.4 | The simulator can misbehave on purpose: duplicates, late rows, rows deleted for good, keys rewritten, fields added and removed, bursts of events, and refused, failed, slow and dropped calls and a limit reached. | M1 |
| R13.5 | A conformance check that every connector must pass to be called beta or stable. | M1 |
| R13.6 | Connectors install as separate packages. Someone else's connector works without changing the product. | M1 |
| R13.7 | A program installed inside a private network connects out to the server and reads or writes there on its behalf. | M2 |
| R13.8 | More connectors, as contributors need them: business applications, cloud warehouses, message queues, file transfer, spreadsheets. | M2 |
| R13.9 | The simulator reads from fixture files or generates data from a description with a fixed seed, so runs repeat. Its sinks keep what they received, for tests to check. | M1 |
| R13.10 | Connectors share one way of calling web APIs, with retries, budget metering and secrets kept out of logs built in. | M1 |
| R13.11 | Every template ships with code, per-environment settings, simulated data, tests and a description. | M1 |
| R13.12 | Connections that sign in with OAuth2 get, refresh and share their tokens across workers, so a system is not asked for a new token by each. | M1 |

### Area 14 — Tenants

| ID | Requirement | M |
|---|---|---|
| R14.1 | Every stored item carries a tenant. An install with one tenant never shows it. Nothing built may assume there is only one. | M1 |
| R14.2 | Each tenant has its own connections, secrets, budgets, limits, alert channels, users and roles. | M2 |
| R14.3 | Tenants are kept apart by the database as well as by the application, and one tenant can't starve another of workers or budget. | M2 |
| R14.4 | A sandbox tenant is created, and refreshed, from production in one step: it copies the setup, never production's secrets, and its changes are promoted back to production after a preview. | M2 |

### Area 15 — Running it

| ID | Requirement | M |
|---|---|---|
| R15.1 | One command starts everything on a laptop with a demo flow, reloads on a change, and opens the dashboard. | M1 |
| R15.2 | Production runs from a container setup of at most four containers, with no cluster manager required. | M1 |
| R15.3 | Upgrades change the database forwards only and need no downtime. | M1 |
| R15.4 | Stored data is cleaned up to a retention policy, and its growth is managed. | M1 |
| R15.5 | Backup, and a restore to a point in time — before a mistake, for instance — that is rehearsed and timed. | M1 |
| R15.6 | A documentation site: getting started, concepts, an operating guide, and a reference for every connector, template, command and API, with examples that are tested. | M1 |
| R15.7 | Releases are versioned by meaning, published as packages and as signed container images with a list of what they contain. | M1 |
| R15.8 | A contribution guide, a code of conduct, a way to report a security problem privately, and named owners for security-sensitive code. | M1 |
| R15.9 | A deployment chart for a cluster manager. | M2 |
| R15.10 | Each kind of stored data has its own default keeping time, which can be changed: read data until every route has taken it and some days more, delivery history for months, the audit log for years. | M1 |
| R15.11 | Capacity grows by adding worker processes. A worker asked to stop finishes what it is doing first. | M1 |
| R15.12 | Written procedures for the common troubles: failed deliveries, a budget used up, database growth, a restore, an upgrade, changing a secret. | M1 |
| R15.13 | A sizing guide: what volume each deployment size carries. | M1 |
| R15.15 | The server listens only on its own machine unless told otherwise, and warns when it is. It is reached through a proxy that encrypts traffic. Images hold no secret, and the setup refuses to start without its secret key. | M1 |
| R15.16 | When the database is missing, out of date or unreachable, or a port is taken, every command says what is wrong and what to do, never a stack trace. | M1 |
| R15.14 | The one-command local stack runs without a container runtime. | M2 |

## 8. Hard cases

Each must pass before the milestone it belongs to is released.

| ID | Case | Expected | M |
|---|---|---|---|
| HC-01 | A record moves to another slice because a date on it was edited | No stale copy is left where slices are replaced whole | M1 |
| HC-02 | A table with no change stamp | Added, changed and deleted rows are all found | M1 |
| HC-03 | A source rewrites a key in place | The business key keeps exactly one current row | M1 |
| HC-04 | Rows become visible late, inside the look-back | Each is captured once, with no repeat deliveries | M1 |
| HC-05 | Rows are back-dated into a closed period | The scheduled full comparison captures them | M1 |
| HC-06 | A destination is down while its source can be read | The read completes; deliveries catch up afterwards | M1 |
| HC-07 | A high-priority reader and a low-priority writer share one budget | The limit is never exceeded; the reader keeps its share | M1 |
| HC-08 | A daily limit is used up | Work waits for the next window and is shown waiting, not failed | M1 |
| HC-09 | A worker is killed in the middle of a business operation | Nothing is posted twice; it can be reversed on request | M1 |
| HC-10 | A record set aside is overtaken by a newer version of the same key | It is resolved as replaced | M1 |
| HC-11 | A route is added to a live flow | It first receives history, then follows live | M1 |
| HC-12 | A dataset's shape changes | An added field passes; a dropped field waits for a person | M1 |
| HC-13 | Two related feeds, headers and lines, arrive on their own | Neither holds the other up; readiness makes only the flows that asked wait | M1 |
| HC-14 | Ten times the normal rate of webhooks | Nothing is lost; delay returns to normal within 5 minutes | M1 |
| HC-15 | New code is deployed while deliveries are in progress | Nothing is lost or delivered twice | M1 |
| HC-16 | The process that starts readiness-triggered flows is killed while starting one | The flow runs exactly once for that period | M1 |
| HC-17 | Data arrives after its period was closed | It is run again once, warned about or ignored, as the flow says | M1 |
| HC-18 | A looked-up dataset gets a new version while a delivery is being applied | That delivery uses one state throughout and records it; the next uses the new one | M1 |
| HC-19 | A record's looked-up row is missing, then added | It is delivered or filtered as the query says; a replay afterwards delivers it complete | M1 |
| HC-20 | A value takes effect on a future date with no change at the source | Nothing before the date; exactly once on the date; nothing new on a repeat | M1 |
| HC-21 | A read is due outside a connection's hours while a webhook arrives | The read waits visibly; the event is stored at once and delivered when hours open | M1 |
| HC-22 | A database change stream is interrupted and resumed | No change is lost or applied twice | M2 |

## 9. Quality targets

| ID | Target | Checked by | M |
|---|---|---|---|
| Q-01 | Webhook received to destination updated: 30 s or less for 95 in 100 events (aim: 5 s), at 50 events a second | Performance tests | M1 |
| Q-02 | At least 20,000 rows a second per worker from source to spool | Performance tests | M1 |
| Q-03 | At least 5 million records a day per environment on the smallest supported deployment | Performance tests | M1 |
| Q-04 | No delivery lost or doubled when any process is killed, the database restarts, or the network is slow | Fault tests | M1 |
| Q-05 | A server restart costs a running task at most one retry. At most 5 minutes of data lost and 1 hour to restore after a failure | Fault tests, restore rehearsal | M1 |
| Q-06 | From a clean install, a demo flow is on the dashboard within 5 minutes | Release checklist | M1 |
| Q-07 | One required database, with no extensions, so a managed one works | Design review | M1 |
| Q-08 | The code that flows are written against is fully typed; test coverage gates are enforced in CI | CI | M1 |
| Q-09 | From the first release, deprecated features keep working for at least two minor releases | Release process | M1 |
| Q-10 | The server meets a recognised application-security standard at its second level; no known critical or high vulnerability at release | Security review, CI scans | M1 |
| Q-11 | An operator recovers a failed delivery in 5 clicks or fewer, with no command line or SQL | Usability test | M1 |
| Q-12 | Container images for the two common processor families. Development works on Windows, macOS and Linux | CI | M1 |
| Q-13 | The dashboard's main pages meet WCAG 2.1 level AA, in light and dark | Automated accessibility checks | M1 |
| Q-14 | Every connector and template has reference documentation and an example that CI runs | Documentation CI | M1 |
| Q-15 | The smallest production deployment runs on one machine, with no paid licence | Design review | M1 |
| Q-16 | A 100-million-row extract completes using the object-storage spool | Performance tests | M2 |
| Q-17 | With several tenants, a request with another tenant's ids is refused on every address and tool | Cross-tenant tests | M2 |
| Q-18 | A webhook is acknowledged within 200 ms, whatever its destinations are doing | Performance tests | M1 |

## 10. Limits the product keeps

- **Licence.** MIT. Nothing it ships may depend on code under a licence that would force its terms on users.
- **No cluster manager required.** Everything runs without one.
- **Connections out only from a private network** (R13.7).
- **Seconds, not milliseconds.** "Near real time" means seconds.
- **Drivers that can't be redistributed** are installed by the user, never shipped.

## 11. Decisions to make

Each is settled by the first change that needs it, through that change's ADR step, and recorded
in `adr/`. The walking skeleton (issue #4) settled D-01, D-12 and the first half of D-02, and the
storage foundation (issue #12) D-05; `AGENTS.md` § Project lists the stack and the conventions that
follow from them.

| ID | Decision | Needed by |
|---|---|---|
| D-01 | Server framework and how pages are rendered and refreshed | **Settled:** [ADR 0003](../adr/0003-pages-rendered-on-the-server.md) |
| D-02 | The required database, and whether it also holds the spool | The database is **settled:** [ADR 0004](../adr/0004-postgres-18-only.md). The spool: the first change that stores data |
| D-03 | How durable execution is provided: an existing engine behind a small interface of our own, or our own | R6.1 |
| D-04 | The data model: dataset, record, partition, version, route and ledger for both batches and events. Events are not tied to webhooks: database change events (R3.15, M2) must fit in as one more source of events, resumed from where they stopped, with no redesign | Area 3 |
| D-05 | Environment as deployment, tenant as namespace; how light tenancy is in M1 | **Settled:** [ADR 0009](../adr/0009-tenants-on-every-row.md) |
| D-06 | How flows are packaged, installed and switched without a restart | Area 2 |
| D-07 | How agents reach the product: the protocol, and one service layer under the dashboard, the API and the agent tools | R12.2 |
| D-08 | How it is deployed: the container setup and the one-command local stack | The container setup is **settled:** [ADR 0015](../adr/0015-container-setup.md). The one-command local stack: R15.1 |
| D-09 | How long versions are kept by default, and the archive policy | R3.5 |
| D-10 | The public home: package name, image registry, documentation address | Package names **settled:** [ADR 0008](../adr/0008-fcon-technical-names.md). The registry and the documentation address: R15.7 |
| D-11 | Who maintains it, and how reviews and releases are run | R15.8 |
| D-12 | The lowest supported language version | **Settled:** [ADR 0001](../adr/0001-python-3-14-only.md) |
| D-13 | Whether a transform runs when a route delivers, or its result is stored as a version of its own | Area 4 |
| D-14 | Whether one service layer sits under the dashboard, the API and the agent tools, so rights, previews and audit are the same for all three | Rights **settled:** [ADR 0016](../adr/0016-users-roles-and-one-rights-check.md). Previews and audit follow the same layer: R8.6 |

## 12. Not planned

A visual flow designer; turning the whole dashboard into a single-page application; a hosted
service; an API gateway or developer portal; full business-process management; a marketplace of
connectors; column-level lineage; an optional streaming transport; a visual data-mapping assistant.
A piece moves into a milestone only when the owner brings it forward.

## 13. Milestones at a glance

| Milestone | In one line |
|---|---|
| **M1** | The whole core: writing, packaging, moving and transforming data, scheduling, reliability, the dashboard that watches and acts, environments with protection, security, alerts, read-only AI, general-purpose connectors, and what a release needs |
| **M2** | Database change events, the object-storage spool, running-time overrides, freshness views, export of metrics, secret services, the private-network program, AI that acts, an in-dashboard assistant, full tenancy, sign-in through an identity provider, the multi-environment page, a cluster chart, a data API that other systems ask for data, endpoints through which the hub stands between two systems, erasing a person's data (by early 2027), business calendars, documents passing through, subscribing to event buses, other systems subscribing to the hub's events, and more connectors |

M1 is large. It is built one issue at a time, in the order of areas 1 to 15, starting with a
walking skeleton: the app starts, answers a health check and shows a sign-in page.
