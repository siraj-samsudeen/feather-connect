## Why

Nothing runs yet. Every later feature needs a server that starts, that the host it runs on can
check, and that shows a first page, with the tests and CI that prove it. This change is that
thinnest slice through every layer, the walking skeleton of the catalogue's § 13, so each later
issue only adds to something that already starts, is tested and passes CI.

What people get: an administrator who starts the server is told in plain words when a setting is
wrong; a host or an uptime monitor can tell whether the server is running and ready; anyone who
opens the dashboard gets a sign-in page that works on a phone, with JavaScript off, and in light
and dark.

## What Changes

- The `feather server` command starts the server. Its settings come from `FEATHER_*` environment
  variables, and from a `.env` file in development.
- Health and readiness addresses for the host and for monitors. Ready means the database answers
  and is Postgres 18 or later.
- A sign-in page that refuses every attempt for now (there are no users yet), a not-found page and
  a server-error page, with safety headers on every page.
- Clear messages at start-up: a wrong setting stops the server; a database problem leaves it
  running but not ready, until the database is fixed.
- The project's skeleton: a uv workspace of three packages, the acceptance suite, CI on GitHub
  Actions, one development database in Docker shared by every worktree, and a script that gives
  each worktree its own ports and database.
- Seven ADRs, and the catalogue's decisions D-01, D-12 and the first half of D-02 marked settled.

## Capabilities

### New Capabilities

- `logs-and-health`: whether the server is running, and whether it is ready to take work, at
  fixed addresses a monitor can check.
- `users-and-access`: the sign-in page; a refused sign-in never says whether the name or the
  password was wrong.
- `dashboard-basics`: promises every page keeps: it works with JavaScript off, is accessible in
  light and dark (following the computer's setting), is usable on a phone, and an address that does
  not exist gets a page that says so.
- `local-development`: start-up problems explained in plain words, never a stack trace.

### Modified Capabilities

None: there are no specs yet.

## Impact

- Code: `packages/feather-connect` (the flow library), `packages/feather-server` (the server and
  its pages) and `packages/feather-cli` (the `feather` command), in one uv workspace with one lock
  file.
- Dependencies: FastAPI, Jinja2, Uvicorn and psycopg 3 with its pool; ruff, pyright, pytest,
  vulture and deptry for development. The acceptance suite has its own: behave, Playwright and
  axe-core.
- New files: `compose.yaml`, `.env.example`, `scripts/worktree_env.py`, `acceptance-tests/`,
  `.github/`, and `adr/0001` to `adr/0007`.
- `AGENTS.md` § Project: the stack lines confirmed, the worktree ports, and a list of conventions.
- `docs/requirements.md` § 11: D-01, D-12 and the first half of D-02 settled.
- Not in this change: real sign-in and users (R10.1), the secret key (R15.15), the one-command
  local stack (R15.1), container images (R15.2).
