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

### An operator's value is for a name the code no longer has

- **What it means:** a new package version no longer declares a flow, dataset or route that an
  operator had set a value for. The value is kept, never dropped, and does nothing until a later
  version declares that name again. Recording the version printed a warning, and the server's
  log has a `fcon.catalog` warning naming it.
- **First checks:** `fcon settings list` shows every operator value, flagged "no longer in the
  code"; ask the package's developer whether the name was renamed without `renamed_from`.
- **What to do:** if the name was renamed, set the value again on the new name; then, or if the
  name is gone for good, `fcon settings clear <name> <setting> --reason "..."`.

## Alerts

None yet. Each alert a change adds gets an entry here: what it means, who is affected, first
checks, what to do, and when to escalate.
