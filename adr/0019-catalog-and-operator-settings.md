# 0019. The catalog is written from the code, one stable entry per name; operator settings sit beside it

- Status: accepted
- Date: 2026-11-28
- Decision-makers: the project owner
- Decided in: issue #31, point 2 and its review rounds; built in issue #34

## Context and Problem Statement

Flows, datasets and routes are Python code in versioned packages (R1.1, R2.1). The dashboard,
the history of every version and delivery, and an operator's settings all need to name them
when no host runs that code, and across package versions. The owner's principle: code is for
logic, settings are for operators, so an operator changes a schedule, a look-back or a pause per
environment with no new package (R2.9). Once versions and deliveries point to these rows, their
shape is hard to change.

## Considered Options

- A catalog written from the code at install: one stable entry per full name (R2.6), whose id
  never changes, a rename only when the code names the old name (`renamed_from`); each package
  version keeps its own copy of every definition; operator settings in a table beside it, one row
  per entry and setting; the settings an operator owns listed in code, with their types and
  defaults.
- The code only, read from the running package (the dashboard breaks when no host runs that
  version; no history).
- Definitions written in the dashboard or in YAML (against R1.1).
- Settings keyed by the name text, or one document of overrides per entry.

## Decision Outcome

Chosen option: "a catalog written from the code, one stable entry per name, settings beside it",
because history and settings follow an entry by its id through upgrades and explicit renames,
every package version's definitions stay readable after it is replaced (R2.19), and one row per
setting gives each change its own audit record and row version. The effective value is the
operator's, else the code's, else the product's default, and each value shows its layer (R1.9).
A recorded package version never changes (R2.12). An operator's value for a name the code no
longer has stays, flagged. Until package versions can be switched on (area 2), the latest
recorded version of a package is its current one. `tzdata` (the Python Software Foundation's
copy of the IANA time zone database, released with each IANA update) becomes a direct
dependency of `fcon-server`, so a setting's time zone resolves the same way on every platform,
including Windows and a slim container.

### Consequences

- Good, because #35's versions and #36's deliveries point to a stable dataset and route, and
  record the package version that made them, with no redesign when a name changes.
- Good, because a new setting is one line in the code's list, with no migration.
- Good, because definitions are kept whole as data, so readiness sets, an event's kind and
  versioned shapes (#31 § Room left for later) are recorded without a new table.
- Bad, because the settings list is made before the features that read it; renaming a setting
  later needs a step that moves operator values.
- Bad, because "latest recorded is current" must be replaced when versions are switched on per
  flow (R2.4).
- Rejected: the code only, with no history; definitions in the dashboard or YAML, against R1.1;
  settings keyed by name text, which a rename would have to rewrite in every table; one document
  per entry, which locks and rewrites every setting for one change.
