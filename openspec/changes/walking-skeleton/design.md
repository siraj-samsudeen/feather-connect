## Context

Nothing runs yet. This change builds the walking skeleton: the server starts, answers health
checks and shows a sign-in page, with every check and CI job that later changes build on (see
`proposal.md`). The owner agreed its design with the manager session in issue 4, point by point,
on 21-Nov-2026. That checklist is copied below word for word, so the repo keeps every decision
once this change is archived; the issue stays as the record of the discussion. The ADRs
`adr/0001` to `adr/0007` carry the reasons for the seven decisions that are hard to undo.

After the checklist, this file says how the skeleton is built, and records the three decisions
the checklist left to the build. No ADR is in force yet: `adr/` is created by this change.

## Agreed design (issue 4, owner, 21-Nov-2026)

1. A uv workspace at the repo root with three packages from the start (owner, 21-Nov-2026): `packages/feather-connect` (the flow library, `import feather_connect as fc`), `packages/feather-server` (the server and its pages) and `packages/feather-cli` (the `feather` command). The flow library never imports the server or the command line, and a test checks it. One lock file; the end-of-change checks run over all three. Python 3.14 only, for development and for the deployed server, which runs in a container on a cloud host (owner, 21-Nov-2026); `requires-python = ">=3.14"`. `uv run` for every command.
2. The server (owner, 21-Nov-2026):
   - FastAPI with Jinja2 templates, and HTMX to refresh part of a page (D-01).
   - Served by Uvicorn, one process per container; the host or container runtime restarts it and adds copies.
   - Started by `feather server`, which reads and checks its settings, logs where it listens, and runs Uvicorn in the same process.
   - Listens on `127.0.0.1` by default and warns when it listens beyond its own machine (R15.15); the container image sets `FEATHER_HOST=0.0.0.0`.
   - Port: `FEATHER_PORT`, else the host's `PORT`, else `8080`.
   - Settings come from `FEATHER_*` environment variables only (`FEATHER_HOST`, `FEATHER_PORT`, `FEATHER_DATABASE_URL`); in development also from a git-ignored `.env` file. `--host` and `--port` override them for one run.
3. Health checks (R11.4; owner, 21-Nov-2026):
   - `GET /healthz` answers 200 `{"status": "alive"}` while the process is up, and never touches the database, so a database outage does not make the host restart the server.
   - `GET /readyz` answers 200 `{"status": "ready", "checks": {"database": "ok"}}` when a simple query answers within 2 s, else 503 `{"status": "not ready", "checks": {"database": "unavailable"}}`: one word for every database problem (unreachable, login refused, missing, older than 18), as agreed in point 5.
   - Both are open to anyone and never reveal the database's address, user, version or error text; the real error goes to the server's log only.
   - The check that the database's tables are at the expected version is added by the first change that creates tables. Worker health is not part of readiness; it belongs on the dashboard (R7.14).
4. The database. The server only connects to it here; no tables yet.
   - Version (owner, 21-Nov-2026): Postgres 18 and later is the only database. Development and CI run 18, kept on its latest bug-fix release (18.6 fixed wrong results from range partitions with a default partition). Moving to 19 is a later, ordinary change, once 19 has had a few bug-fix releases.
   - The server reads the database's version when it connects. Older than 18: `/readyz` says not ready, and the log says which version it found and that 18 or later is needed (wording under point 5).
   - The deployment guide, written with the container setup (R15.2), says to choose the host's Postgres 18 image: a host's one-click template may still default to an older version.
   - Development (owner, 21-Nov-2026): one Docker container shared by every worktree, from `compose.yaml` at the repo root, with a fixed project name (Compose otherwise names a project after its folder, so each worktree would start its own copy). The Debian-based `postgres:18` image, which sorts text like most hosts do. Published on `127.0.0.1:5442` only: local installs take 5432 to 5439, Windows reserves high port ranges, and Docker otherwise publishes on every network interface. The volume is mounted at `/var/lib/postgresql`, because the 18 image keeps its data under `/var/lib/postgresql/18/docker`. A readiness health check. User and password `feather`/`feather`, for the developer's machine only.
   - Nothing in the code depends on Docker: any Postgres 18 works through `FEATHER_DATABASE_URL`, which goes to psycopg unchanged, so `sslmode=require` and the like work. The log shows the database's host, port and name, never the password (R10.3).
   - Worktrees and tests: each worktree's `.env` names its own database (`feather_issue_<n>`), created once with `docker compose exec db createdb -U feather feather_issue_<n>`. Each test run creates a throwaway database and drops it at the end. No test stops the shared database. With no database running, the database tests fail with "start the database: docker compose up -d"; they never skip.
   - Driver: psycopg 3 with its connection pool, and plain SQL in one store layer; no object mapper.
   - Sync database calls: one store for the server, the workers and the command line; FastAPI runs plain routes in its thread pool. An async route only where a later page needs one.
   - No Postgres extensions required, so any managed Postgres 18 works.
   - Decided later, by the first change that stores data: the upgrade tool and the first tables; which package holds the store; whether the spool lives in Postgres (the rest of D-02); the pool's size; backups (R15.5); text columns with the built-in `pg_c_utf8` collation, so sorting is the same on every platform.
5. Problems at start-up and an unusable database (R15.16; owner, 21-Nov-2026):
   - Settings mistakes stop `feather server` with exit code 2: `FEATHER_DATABASE_URL` missing or not a Postgres address, a port that is not a number, a port already taken. Only a person can fix them.
   - Database problems let it start, not ready: unreachable, login refused, the database missing, Postgres older than 18. It keeps retrying in the background and is ready again by itself once the database is fixed.
   - Every message says what is wrong and what to do. It names the database by host, port and name, never the password, and gives the development hints (`docker compose ...`) only when the database is on the same machine. The texts are fixed, come from one error helper in `feather-cli` that every later command uses, and each is pinned by a test:
     ```
     error: FEATHER_DATABASE_URL is not set.
       Set it to your Postgres 18 address: postgresql://user:password@host:5432/feather
       For development: copy .env.example to .env, then run: docker compose up -d

     error: port 8080 on 127.0.0.1 is already in use.
       Stop the program using it, or pick another port: FEATHER_PORT=8081 (or --port 8081)

     warning: cannot reach the database at 127.0.0.1:5442 (connection refused). Not ready.
       Start it: docker compose up -d

     warning: the database feather_issue_4 does not exist on 127.0.0.1:5442. Not ready.
       Create it: docker compose exec db createdb -U feather feather_issue_4

     warning: the database at db.internal:5432 refused the login of user feather. Not ready.
       Check the user and password in FEATHER_DATABASE_URL.

     warning: Postgres 16.4 found at db.internal:5432; Feather Connect needs 18 or later. Not ready.
       Upgrade the database, or point FEATHER_DATABASE_URL at a Postgres 18 server.
     ```
   - Logs: readable text on a terminal, one JSON object per line elsewhere; `FEATHER_LOG_FORMAT=text` or `json` overrides. The server's own lines and Uvicorn's go through one logger (standard `logging` with a small JSON formatter of our own). Successful `/healthz` and `/readyz` requests are not logged. A database problem is logged when it starts, once a minute while it lasts, and when it ends.
   - A real bug prints one line saying it is a bug, then the traceback, and exits with code 1. A web request that fails inside the server answers 500 with a plain error page, never a traceback.
   - Tables older than the code (the rest of R15.16) come with the first tables.
6. The sign-in page (owner, 21-Nov-2026):
   - `GET /sign-in` shows the product name, "Sign in to continue", user name, password and a Sign in button, as a centred card (layout A of the mockups); on a narrow screen the card becomes the page. Visitors who are not signed in see no version number.
   - Submitting posts the form to `/sign-in`. There are no users yet, so every attempt is refused with "The user name or password is wrong.": the same words for a wrong name and a wrong password, as the finished sign-in keeps them. The page title then starts with "Sign-in failed", and the message is linked to the form. Nothing changes, so the form needs no token yet; the token and the slowing of failed attempts come with real sign-in (R10.7, R10.12).
   - Light and dark follow the computer's setting; no switch yet (R7.11).
   - Our own small stylesheet with colour tokens: no build step, no CSS framework. The computer's own fonts; no icons yet.
   - Every page sends safety headers from the start: a content policy that refuses inline scripts and styles (R10.7), no framing by other sites, no caching of the sign-in page, `nosniff`, a strict referrer policy.
   - Real labels; `autocomplete="username"` and `current-password`; a clearly visible keyboard focus; AA contrast in both themes; usable from 320 px wide and with JavaScript off (R7.10). The automated WCAG 2.1 AA check passes in both themes (Q-13).
   - HTMX is not loaded yet; the first page that refreshes part of itself adds it.
7. The front door and missing addresses (owner, 21-Nov-2026):
   - `/` sends a visitor to `/sign-in` with a temporary 303 redirect, so `/` can later become the overview for signed-in people.
   - An address that does not exist gets the product's own "Page not found" page with status 404, in the same card as sign-in, with a link to sign-in; it does not repeat the address. A failure inside the server gets the "Something went wrong" page with status 500 (point 5). The health checks keep answering JSON; later API addresses under `/api/` answer errors in the API's JSON shape (R8.9).
   - `HEAD` is answered wherever `GET` is, because some uptime monitors check with `HEAD` (FastAPI answers 405 by default).
   - Every redirect is relative (`Location: /sign-in`), and there is no automatic trailing-slash redirect: `/sign-in/` gets the not-found page. FastAPI's default builds a full `http://` address from what the server saw, which behind a host's `https` proxy sends a visitor to the insecure address.
   - With real sign-in, not here: trusting the proxy's forwarded headers (also needed to slow failed sign-ins by address, R10.12), and `?next=` accepting only addresses on this site, so a link cannot send someone elsewhere after signing in.
8. The acceptance suite (owner, 21-Nov-2026):
   - `acceptance-tests/` is its own uv project, as the Python pack sets it up, on Python 3.14. It never imports the product's code, and its tools never reach the product's packages.
   - It creates a throwaway database, starts `feather server` on `ACCEPTANCE_PORT`, waits until `/readyz` says ready, and drops the database at the end. For the outage scenario it starts a second server on a free port chosen at run time, pointed at another free port where nothing listens, and waits on `/healthz`; the shared database is never stopped.
   - Scenarios (what someone sees; message texts, headers and the version check are pinned by pytest):
     1. Running and ready: `/healthz` alive, `/readyz` ready.
     2. Not ready while the database is away: alive, not ready, `unavailable`, no address in the reply.
     3. A monitor checks with `HEAD`: `HEAD /healthz` answers 200.
     4. The front door leads to sign-in: `/` lands on the sign-in page with the name, user name, password and the button.
     5. A sign-in is refused with the same words: "The user name or password is wrong.", page title starting "Sign-in failed".
     6. Signing in with JavaScript off: scenario 5 with JavaScript off.
     7. Accessible in light and dark: axe finds no WCAG 2.1 AA problem on the sign-in, refused and not-found pages, in both themes.
     8. Usable on a phone-width screen: at 320 px nothing scrolls sideways and the button can be reached.
     9. A missing page: `/runs/42` shows "Page not found" with a link to sign-in.
     10. Starting without a database address: `feather server` stops with exit code 2 and the two-part message.
     11. Starting on a port that is taken: it stops, naming the port and how to pick another.
   - The appearance follows the computer's setting in this change; the later change that adds a switch modifies that requirement (the draft spec's "remembered as the user chose").
   - Accessibility: axe-core through `axe-playwright-python`, put in through Playwright's own channel, so the content policy is never loosened for tests. Any error in the browser's console fails a scenario, which catches a script or style the policy blocks.
   - Chromium at 1280 px, plus the one 320 px check of scenario 8. From the pack: the HTML report, screenshots of failed steps, recordings of failed scenarios (on by default in CI), `VIDEO=1`, `HEADED=1`.
9. CI on GitHub Actions (owner, 21-Nov-2026):
   - Runs on every push to a PR branch and every push to `main`; a newer push cancels the older run on the same branch.
   - Jobs, side by side:
     1. Checks, on Linux: `ruff check`, `ruff format --check`, pyright in strict mode, vulture (with a short reviewed list of allowed names, such as handlers only a decorator calls), deptry.
     2. Tests, on Linux with a Postgres 18 container: pytest with 100% coverage across the three packages. A line that runs on one operating system only, or cannot happen, may be marked with a reason.
     3. Acceptance, on Linux with Postgres 18 and Chromium: the suite of point 8. A failed run carries the report, screenshots and recordings for download.
     4. Other systems: pytest on Windows and macOS (Q-12), leaving out by name the tests marked as needing a database, which run on Linux.
     5. Specs: `openspec validate --specs` (OpenSpec 2.0.0 on Node, in CI only; the product has no Node) and the Gherkin extraction.
   - Relaxed until the M1 release, to keep work fast (owner, 21-Nov-2026); #5 tightens them before the release:
     - mutation testing (mutmut) runs weekly on `main` as a report that blocks nothing;
     - the Windows and macOS job runs on every PR and shows red when it fails, but does not block;
     - Dependabot proposes updates monthly, one grouped PR per kind (GitHub's security alerts still arrive at once).
   - ruff's rules: the defaults plus security (`S`), bug-prone patterns (`B`), import order (`I`) and modern syntax (`UP`).
   - Workflow safety: every action pinned to its full commit id, a workflow token that can only read the repo, no secrets. uv's cache and Playwright's browser download are kept between runs.
   - After the first run, `main` requires the checks, tests, acceptance and specs jobs to pass, and changes to come through a PR. Only a repo admin can set this.
10. Worktrees and the project's rules (owner, 21-Nov-2026):
   - Ports per worktree, from the issue number: development `18000 + n`, acceptance `19000 + n` (issue 4: 18004 and 19004). The main checkout keeps 8080 and 8030.
   - `uv run scripts/worktree_env.py <n>` writes the worktree's `.env` (both ports and the database address) and creates `feather_issue_<n>`; with `--drop` it removes that database when the worktree goes. One Python file that works the same on Windows and Linux; `feather dev` (R15.1) may take it over later.
   - The project's rules live in `AGENTS.md` § Project, which every AI tool reads, Codex included (#6 moves them there from `CLAUDE.md`). This change confirms its *(proposed)* stack lines: Python 3.14 only; FastAPI and Jinja2 under Uvicorn, one process per container, HTMX from the first page that refreshes part of itself; Postgres 18 and later as the only database, in one shared Docker container on `127.0.0.1:5442` for development, a database per worktree. Tooling: pyright strict, the chosen ruff rules, the three checks relaxed until M1 (#5), the worktree ports above.
   - A Conventions list in `AGENTS.md` § Project, one line each, with the reasons in the ADRs:
     1. Settings come only from `FEATHER_*` environment variables, and from `.env` in development.
     2. Every command reports problems through the error helper in `feather-cli`: what is wrong and what to do, never a password, never a traceback for an expected problem.
     3. One logger: text on a terminal, one JSON object per line elsewhere.
     4. Templates have no inline `<script>` and no `style=""`: the content policy refuses them.
     5. Redirects are relative.
     6. The flow library never imports the server or the command line.
     7. Database calls are sync, through psycopg, with plain SQL in the store layer.
     8. Tests that need a database are marked as such, and never skip.
     9. Examples and names are generic: no real organisation, customer, vendor system or site.
   - The change's `design.md` copies this issue's agreed checklist word for word, and the ADRs carry the reasons, so once the change is archived the repo holds every decision; this issue stays as the record of the discussion.
11. The ADRs (owner, 21-Nov-2026):
   - Seven, one per decision that is hard to undo, in `adr/`, numbered 0001 to 0007:
     1. Python 3.14 only, for development and the deployed server (D-12).
     2. Three packages, and the flow library imports neither of the others.
     3. Pages rendered on the server: FastAPI and Jinja2, HTMX for parts of a page, Uvicorn with one process per container (D-01).
     4. Postgres 18 and later is the only database, with no extensions (the first half of D-02; where the spool lives stays open).
     5. psycopg, with sync calls and plain SQL; no object mapper.
     6. Settings come only from environment variables.
     7. A strict content policy on every page from the first one: no inline scripts or styles.
   - Everything else agreed here goes in the change's `design.md`.
   - Format: MADR minimal (the project's `preferred-style`), with a header giving the status, the date and who decided. An accepted ADR is never edited; a changed decision gets a new ADR that supersedes it.
   - The change marks D-01, D-12 and the first half of D-02 as settled in `docs/requirements.md` § 11, linking their ADRs.
   - The questioning of each decision happened in points 1 to 10 of this issue, so the owner approves the seven drafts together, and any can be changed on request. Each ADR names this issue as where it was decided. No adversarial review: these record choices already argued through, and the one about security makes the product stricter.

Not in this issue: signing in, users and tokens (R10.1), including how the first administrator is made, which the catalogue does not say yet and that issue adds, the secret key and the refusal to start without it (R15.15), the one-command local stack with a demo (R15.1), container images (R15.2, Q-12), and every area 1–14 feature. Each gets its own issue.

## How it is built

```mermaid
flowchart LR
  person["Administrator or developer<br/>at a terminal"]
  visitor["Visitor<br/>in a browser"]
  monitor["Host or uptime monitor"]
  subgraph process["One feather server process per container"]
    cli["feather-cli<br/>the feather command: settings, logging,<br/>error helper, database watch"]
    server["feather-server<br/>FastAPI app under Uvicorn:<br/>pages, health, readiness, database check"]
  end
  library["feather-connect<br/>the flow library<br/>imports neither"]
  db[("Postgres 18 or later")]
  person -->|"feather server"| cli
  cli -->|"creates the app, runs Uvicorn"| server
  cli -->|"watches it with the server's check"| db
  visitor -->|"sign-in and every other page"| server
  monitor -->|"health and readiness"| server
  server -->|"readiness: one query"| db
```

- One process: `feather server` reads and checks its settings, sets up logging, binds the port,
  starts the database watch, then runs Uvicorn on that socket.
- Dependencies point one way: feather-cli imports feather-server; feather-connect imports neither,
  and a test checks it.
- The server never writes a message for a person: it answers HTTP. Every message a person reads
  comes from the error helper in feather-cli (decision 1).
- Assumption: the host puts an HTTPS proxy in front (R15.15); trusting its forwarded headers comes
  with real sign-in.

Start-up, in order:

```mermaid
sequenceDiagram
  participant P as Person or host
  participant C as feather server (feather-cli)
  participant S as App (feather-server)
  participant D as Postgres
  P->>C: feather server [--host] [--port]
  C->>C: read FEATHER_* (and .env); a mistake stops it, exit 2
  C->>C: bind host:port; taken stops it, exit 2
  C->>D: database watch starts (background)
  C->>S: create the app, run Uvicorn on the bound socket
  C-->>P: log "listening on http://host:port"
  P->>S: GET /readyz
  S->>D: one query, within 2 s
  S-->>P: 200 ready, or 503 not ready
```

Build notes. These are plain implementation, settled by the tests in `tasks.md`; none is a
decision of its own:

- **Command line:** the standard library's argparse, with its usage errors sent through the error
  helper, so a mistyped option also exits with code 2 and the two-part message.
- **Settings:** a small reader of the `FEATHER_*` variables. A `.env` file in the current
  directory fills in only what the environment does not set. The database address is checked with
  psycopg's own parser, and the log shows its host, port and name only.
- **The port:** the command binds the socket itself, before Uvicorn starts, so a taken port is
  reported through the helper. On Windows it binds with exclusive use: Windows lets a second
  program share a port bound with `SO_REUSEADDR`, which Uvicorn's own binding sets.
- **HEAD:** one small ASGI middleware answers `HEAD` like `GET` without the body, at every address.
- **Safety headers:** one ASGI middleware adds them to every response, errors included: the policy
  of decision 3, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`,
  `Referrer-Policy: same-origin`, and `Cache-Control: no-store` on everything but the stylesheet.
- **Pages:** Jinja2 templates with autoescape, printing what a Python function computed for them.
  One stylesheet with colour tokens, switched by `prefers-color-scheme`.
- **Logs:** one handler on the root logger, text when the output is a terminal and JSON lines
  otherwise; Uvicorn's loggers go through it, and a filter drops successful health and readiness
  requests from the access log.
- **Tests:** pytest in each package, plus a repo-level test of the import rule. A session fixture
  creates `feather_test_<random>` on the server that `FEATHER_DATABASE_URL` names, and drops it at
  the end; tests that need it carry the `database` mark.
- **Acceptance suite:** the Python pack's files. `support/stack.py` creates the run's database and
  starts `feather server`; the outage scenario starts a second server on free ports; a terminal
  page object runs the command for the two start-up scenarios.

## Decisions

### 1. The server package finds database problems; the command reports them

feather-server has one database check. It answers "usable", or one of the four problems of point 5
(cannot reach it, login refused, database missing, older than 18) with the host, port, name and
the driver's own text. `/readyz` runs it live, within its 2 seconds, and answers one word. The
`feather server` command runs the same check every few seconds in a background thread, and logs
through the error helper: when a problem starts, once a minute while it lasts, and when it ends.
So feather-server never imports feather-cli and is tested on its own; feather-cli imports
feather-server only to start it and to call its check (owner, 21-Nov-2026).

Rejected: the server logs its own database problems. It would need the texts of the error helper
in feather-cli, which already imports the server (a cycle), or a second set of texts; and a later
`feather worker` would need the same watch again.

### 2. No connection pool yet: a fresh connection for each check

The readiness check and the watch each open a connection, run one query and close it.

Rejected: open psycopg's pool now, as point 4 names it for the store. Nothing stores data yet, so
the pool would serve only this check, and a pool that cannot connect says only "no connection
within 2 seconds", where the messages of point 5 need the cause ("connection refused", "database
does not exist"). The first change that stores data adds the pool and its size, and readiness then
goes through it.

### 3. The content policy starts from nothing allowed

Every response carries
`Content-Security-Policy: default-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`.
A later page that needs more adds exactly that: HTMX adds `script-src 'self'` and
`connect-src 'self'`.

Rejected: `default-src 'self'`. It is shorter, but it lets any file the product serves run as a
script, load as a frame or be fetched, before any page needs that.

## Risks / Trade-offs

- [libpq gives no error code for a refused login or a missing database at connection time, only
  English text] → the check matches the text of Postgres 18's messages, pinned by tests against a
  real server; a text it does not recognise is reported as "cannot reach the database" with the
  driver's first line, so nothing is hidden.
- [On Windows, psycopg reports a refused connection as a timeout] → when the connection times out,
  the watch tries the port with a plain socket, so the log still says "connection refused".
- [A fresh connection per readiness check] → a monitor every few seconds costs one connection each
  time, which Postgres handles easily; the first store's pool replaces it.
- [axe-core finds about a third of WCAG problems automatically] → labels, keyboard focus and
  contrast are also on the verifier's checklist.

## Migration Plan

None: nothing is deployed yet.

## Open Questions

None.
