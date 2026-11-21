# 0009. A tenant on every row and call; environments as deployments; tenants ready for sandboxes

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #12, point 1 (catalogue decision D-05)

## Context and Problem Statement

R14.1 asks that every stored item carry a tenant, that an install with one tenant never show it,
and that nothing assume there is only one. D-05 asks how environments and tenants relate, and how
light tenancy is in M1. Adding a tenant to tables after data exists means rewriting every key,
every query and every index; leaving it to each issue lets one table forget it.

## Considered Options

- A `tenant_id` column on every table, part of every key, added to every query by the store in
  one place; each environment its own deployment and database; the tenant table ready for
  sandbox tenants.
- One tenant only in M1, with the column added when a second tenant is needed.
- An environment column beside the tenant, so one deployment holds development, test and
  production.
- A database or schema per tenant.

## Decision Outcome

Chosen option: "a tenant on every row and call", because the column costs little now and makes
mixing tenants impossible to build by mistake. Every key starts with `tenant_id`, and a reference
carries the tenant, so the database refuses a row pointing into another tenant. The tenant of a
call comes from who is calling (session or token), never from the address or the body; the same
tenant goes on every log line, audit record, token, session and job, through one context object.
A tenant id is a short fixed name (`default` in M1). Each environment is its own deployment with
its own database (R9.1), named by `FCON_ENVIRONMENT`; there is no environment column. The tenant
table holds a kind (production or sandbox) and the tenant it was made from, so M2's sandboxes
(created and refreshed from production, without its secrets) need no rewrite.

### Consequences

- Good, because a second tenant, row-level security (R14.3) or a sandbox adds rules, not columns.
- Good, because a query that forgets the tenant fails the tests: each test works in a tenant of
  its own.
- Bad, because every key and index is one column wider, and every query names the tenant.
- Bad, because a schema or database per tenant, which separates tenants more strongly, is ruled
  out; row-level security in M2 is the second wall instead.
