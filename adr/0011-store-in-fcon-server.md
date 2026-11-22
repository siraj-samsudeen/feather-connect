# 0011. The store lives in fcon-server, in the fcon schema, never in the SDK

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #12, points 4, 5 and 17

## Context and Problem Statement

The product's own tables, their queries, the migrations and their runner need a home. The flow
library (`fcon-sdk`) never imports the server or the command line (ADR 0002), and flow and package
code must never reach the product's database (R2.17). The product's tables share a database that
a host may also use for other things.

## Considered Options

- The store in `fcon-server` as `fcon_server.store`, with its `migrations/`; the tables in their
  own schema `fcon`, always named in full.
- A fourth package for the store, used by the server and the worker.
- The store in `fcon-sdk`, so flows can reach it.
- The tables in the `public` schema, found through `search_path`.

## Decision Outcome

Chosen option: "`fcon_server.store` and the `fcon` schema", because the server and the future
worker are the only code that reaches the store, and a fourth package is not needed until the
worker has a package of its own; if it does, the store moves to a package both use. The first
migration creates the schema `fcon`; SQL always names tables in full (`fcon.tenant`), so a table
of the same name elsewhere is never picked. Flow and package code never gets the product's
database address; when flows must run without Postgres, the SDK gets an in-memory stand-in and a
definition of what a store offers, met by both and checked by one shared test suite.

### Consequences

- Good, because the SDK stays free of database code, and flows cannot reach the product's data.
- Good, because the product's tables never collide with a host's own.
- Bad, because the store may move to its own package when the worker issue decides it needs one.
- Bad, because every query spells out `fcon.` before each table.
