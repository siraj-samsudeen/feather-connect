# 0016. A user belongs to one tenant, has one role, and rights are checked in one service layer

- Status: accepted
- Date: 2026-11-22
- Decision-makers: the project owner
- Decided in: issue #16, point 2 (catalogue question D-14, for rights)

## Context and Problem Statement

People need to sign in, and each may do only what their role allows (R10.1, R10.2). Everything
the dashboard can do, the API and the command line can do too, under the same rights and the same
audit (R8.6). Every row carries its tenant (ADR 0009), and tenants are kept apart by the database
as well as the application (R14.3). Two shapes are hard to change once users exist: how a user
relates to tenants, and where a right is checked.

## Considered Options

- A user belongs to one tenant (`fcon.user`, key `(tenant_id, id)`); one role per user, as text
  with a check, plus two yes/no grants; one table in code maps each action to the least role it
  needs, and `require(ctx, action)` checks it in the service layer the dashboard, the API and the
  command line all call.
- Install-wide accounts with a membership per tenant.
- A permissions table: roles and rights as rows an administrator edits.
- Each route or command checking rights itself.

## Decision Outcome

Chosen option: "one tenant per user, one role, one rights check in the service layer", because it
keeps every table inside a tenant, matches the four roles and two grants the catalogue names, and
makes a forgotten check impossible to hide behind a different door: the dashboard, the API and
the command line reach the same functions. A person in two tenants has two users, as in the
sandbox model. The roles are `viewer`, `operator`, `developer` and `administrator`; the grants are
`is_hold_approver` and `is_personal_data_reader`. The role is read fresh on every request, so a
demoted user loses rights at once. A refusal is audited (R10.4). Users are never deleted; they
are `active` or `disabled`.

### Consequences

- Good, because no row lives outside a tenant, so the database can keep tenants apart in M2.
- Good, because a right is one line in one table, the same for every way in, which settles D-14
  for rights (previews and audit follow the same layer when they come).
- Bad, because a person who works in two tenants signs in twice, with two passwords, until
  sign-in through an identity provider (R10.8, M2).
- Bad, because a custom role means a code change; the catalogue asks for none.
- Rejected: install-wide accounts, a table outside every tenant (against R14.3); a permissions
  table, more to build and audit for rights nobody asked to edit; checks in each route, where one
  forgotten check opens an action.
