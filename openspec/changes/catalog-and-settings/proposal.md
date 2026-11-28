## Why

Flows, datasets and routes are declared in Python inside packages, but the server has nowhere to
record them, and an operator can't change a schedule or a look-back without a new package. Every
later data-model build (#35 partitions and versions, #36 the ledger, #37 events and readiness)
and the SDK core point to a stable dataset and route, so the catalog comes first (issue #34,
the contract is issue #31 point 2 with its review rounds).

What people get: each flow, dataset and route the code declares is recorded once per package
version, under a name that keeps its identity across versions, so history and settings follow it.
An operator changes what is theirs (a schedule, a look-back, retries, a pause) per environment
with no new package; they see each value in force and whether the operator, the code or the
product's default set it (R1.9, R2.9); every change says who made it and why, with a reason
required in a protected environment (R9.2, R10.4); and an operator's value for a name the code
no longer has is flagged, never dropped.

## What Changes

- **The catalog.** A store-level service records one package version's definitions, given as
  data: each flow, dataset and route, with a stable identity (its full name, such as
  `shop-flows.orders`, R2.6), and each package version keeping its own copy of each definition.
  A recorded package version never changes (R2.12). It is written only by this service; the
  install path (area 2) calls it later.
- **Explicit renames.** A definition that names `renamed_from` keeps the old name's identity, so
  its history and the operator's settings carry over; any other new name is a new entry.
- **Operator settings.** One list in code of the settings an operator owns for each kind (flow,
  dataset, route), with their types and the product's defaults. The effective value is the
  operator's, else the code's, else the default; every change is audited with who and why.
- **Commands, until the dashboard's settings pages come** (a later UI issue):
  `fcon catalog record <file>` (the stand-in for the install path, from a file of definitions),
  `fcon catalog list`, `fcon settings show <name>`, `fcon settings set <name> <setting> <value>`,
  `fcon settings clear <name> <setting>`, and `fcon settings list` (every operator value, flagged
  when its name is no longer in the code). `--reason` on each change.
- **A protected environment**: a new setting, `FCON_PROTECTED` (`on` or `off`, default `off`;
  `on` in the deployment template), under which a change without a reason is refused and the
  refusal audited.
- Four tables in one expand-only migration; rights for seeing and changing settings and for
  recording the catalog, in the one rights table (ADR 0016); ADR 0019.

## Capabilities

### New Capabilities

- `catalog-and-settings`: a package version's flows, datasets and routes are recorded under
  stable names; an operator sees and changes the settings that are theirs, per environment, with
  each value's layer shown and every change audited.

### Modified Capabilities

None.

## Impact

- Code: `fcon_server.catalog` (new: recording, the settings list, the settings service),
  `fcon_server.store.tables` (four tables), a migration, `fcon_server.users.rights` (three
  actions), `fcon_cli` (the `catalog` and `settings` commands, `FCON_PROTECTED`, messages in the
  error helper).
- Dependencies: none new.
- Docs: `adr/0019`, `docs/architecture.md` (the catalog), `docs/runbook.md` (the flagged
  settings), `.env.example` and `deploy/.env.example` (`FCON_PROTECTED`), `AGENTS.md` unchanged.
- How we know it is broken: every catalog and settings change is an audit record, with the
  request id; a refused change is a `refused` audit record. Recording logs one line per package
  version (`fcon.catalog`), naming the package, the version and how many entries, and a warning
  for each operator value whose name the code no longer has. No metric or alert: nothing runs on
  a schedule yet; the flagged values get a runbook entry.
- Room left for later (#31 § Room left for later): definitions are stored whole as data, so
  readiness sets, an event's kind and versioned shapes are recorded with no new table; the
  package version a version or delivery records (#35, #36) is this change's package version row.
- Not in this change: installing packages (area 2), the dashboard's settings pages, readiness
  sets' own rows (#37), connections and their settings, budgets and connection hours (they belong
  to a connection, and budgets to the engine design, D-03).
