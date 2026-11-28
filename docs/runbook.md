# Runbook

What an operator looks at, and what to do, when something is wrong. Written for someone who did
not build the feature. A change that adds an alert adds its entry here (`change-modes`
§ Definition of Done).

## How to look

- **Is it running?** `/healthz` answers while the server process runs.
- **Is it ready?** `/readyz` answers `{"status": "ready", ...}` (200) when the server can also
  use the database; otherwise `{"status": "not ready", ...}` (503), and the host stops sending it
  traffic. It never says why, since anyone can ask: the cause is in the server's log.
- **The database's upgrades:** `fcon db status` lists the upgrades applied, with when they ran,
  and those waiting; it changes nothing. `fcon db upgrade` applies the waiting ones.
- **Logs:** one JSON object per line, each with the `tenant` and a `request_id`; follow one
  request by its id. A password, a session id or a form token never appears in a log line.

## Common situations

### The server is up but not ready

- **What it means:** `/readyz` answers `not ready`: the database can't be reached, or it waits
  for an upgrade.
- **First checks:** the server's log, which names the cause; `fcon db status`; the database's
  own health.
- **What to do:** start or reach the database; or run `fcon db upgrade`. The server becomes ready
  by itself once the database is.

### The record blocks are running out of days

- **What it means:** the server's log warns that the record blocks have partitions for fewer
  than 30 days after today. The stored data keeps each read's records in a table split by UTC
  day, and each upgrade makes the days from today through 90 ahead. When today's is missing,
  the server is not ready: no read can be stored.
- **First checks:** `fcon db status`; when the last upgrade ran.
- **What to do:** run `fcon db upgrade`, even with no upgrade waiting: it makes the missing
  days. The warning goes once the days are there.

### A person says they can't sign in

- **What it means:** usually a mistyped password, or repeated failures being slowed: after 3
  failures in 15 minutes for one name or from one address, each attempt waits, up to a minute.
  No account is ever locked.
- **First checks:** the audit records for that name (refused sign-ins, waits); whether the user is
  disabled (`fcon users list`).
- **What to do:** ask them to wait a minute and try once more. Resetting someone's password
  comes with the user-management pages; until then, a lost password needs a new user.

### The first administrator's password was lost

- **What to do:** on the host, `fcon users add <name> --admin` makes another administrator; the
  command asks for the password.

## Alerts

None yet. Each alert a change adds gets an entry here: what it means, who is affected, first
checks, what to do, and when to escalate.
