# Architecture

The whole system on one page, for a developer new to it. Any change that adds or removes a
service, a store or an outside system updates this page (`change-modes` § Definition of Done).
The diagrams follow the `c4-diagrams` skill. The reasons for each choice are in [`adr/`](../adr/).

## Context: who and what it talks to

```mermaid
flowchart LR
  dev["Developer: writes flows in Python"] --> fc["Feather Connect"]
  op["Operator: runs, monitors and repairs flows"] --> fc
  agent["AI agent: the same, through the same rights"] --> fc
  fc --> src["Sources: the systems flows read from"]
  fc --> dst["Destinations: the systems flows deliver to"]
```

Sources and destinations arrive with the first connectors; each has a fake and a contract test
(#28).

## Containers: what runs, and where data lives

```mermaid
flowchart LR
  browser["Browser"] --> proxy["Caddy: https and certificates (production)"]
  proxy --> server["fcon server: FastAPI and Jinja2 under Uvicorn"]
  cli["fcon command line: users, db upgrade and status"] --> db
  server --> db[("Postgres 18: schema fcon")]
  migrate["fcon db upgrade: one-shot, before the server starts"] --> db
  worker["fcon worker (planned): runs the flows"] -.-> db
```

| Container | What it does | Talks to |
|---|---|---|
| `fcon server` | The dashboard: signed-in pages rendered on the server, `/healthz` and `/readyz` | Postgres |
| `fcon` command line | Adding and managing users, upgrading the database, starting the server | Postgres |
| `fcon db upgrade` | Applies the database's waiting upgrades, under a lock, before the server starts | Postgres |
| Postgres 18 | Every table in the schema `fcon`, each keyed by tenant | — |
| Caddy | In production only: https with automatic certificates, in front of the server | `fcon server` |
| `fcon worker` (planned) | Runs flows: reads from sources, delivers to destinations | Postgres, sources, destinations |

One container image, `fcon`, runs every role; the command decides which (`docs/deploy.md`).

## Code: the three packages

| Package | Holds | Never |
|---|---|---|
| `fcon-sdk` | The library flows are written with | imports the server or the command line |
| `fcon-server` | The web app, the store (database access), users and sessions | is imported by flow code |
| `fcon-cli` | The `fcon` command | holds business rules of its own |
