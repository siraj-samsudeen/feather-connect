# AGENTS.md

- For OpenSpec propose/apply/verify/archive workflows, use the `change-modes` skill: one worktree,
  branch and PR per change, from proposal to archive. It overrides the two-PR flow of the
  upstream `openspec-git-discipline` skill.
- Work starts from a GitHub issue and goes one issue at a time per worker; the manager session
  stays on `main`. See the `issue-workflow` skill (issue body, red/yellow/green rating, blocked by,
  task sessions and worktrees, the UI route).

## Review guidelines

These apply to every review of a change: local reviews before a PR, and PR reviews (Codex's
GitHub reviewer reads this section).

**Stance.** The product evolves fast. Getting the functionality to fit the need matters more than
perfect code. Do not add code, or follow-up issues, for things unlikely to happen.

**Who reviews locally.** Codex, if it is available (`codex review --base main`); otherwise a
review by a different Claude model than the one that wrote the code.

**UI changes take the UI route** (the `issue-workflow` skill): mockups, a numbered checklist in
the issue, then an independent verifier against the real UI, before the owner sees code. A code
review covers only what a person can't see when testing: security, permissions, data, server
logic. No review for docs, cosmetic changes or very minor fixes.

**Adversarial review only with the human's consent.** When the agent judges the work complex or
critical — security, permissions, data — it proposes an adversarial review (or the
`adversarial-authoring` skill for a planning artifact) in one line, with the reason, and runs it
only if the human says yes. It is never mandatory.

**At most 3 review rounds.** After the third, stop and propose the next step to the human instead
of starting a fourth.

**Triage every finding before presenting it:**

1. **Breaks core functionality** — wrong results, data loss, a security hole → fix now.
2. **Plausible in real use, limited impact** → fix it if cheap; otherwise file **one** issue for
   all such findings, not one per finding.
3. **Rare or theoretical edge case** → one line in the PR body under "Deliberately not handled".
   No code, no issue.

Present the findings grouped by these three levels. In a PR review, report level 3 findings as
level 3, not as requests for changes.

## Project

Feather Connect is an open-source (MIT) integration hub: flows written in Python move data from
one source to many destinations, and developers, operators and AI agents run, monitor and repair
them from one dashboard.

**Stack** (owner, 21-Nov-2026; the reasons are in [`adr/`](adr/)):

- Python 3.14 only, for development and for the deployed server, managed with uv: a workspace of
  three packages (`packages/fcon-sdk`, `fcon-server`, `fcon-cli`), one lock file.
- Pages are rendered on the server as HTML: FastAPI and Jinja2 under Uvicorn, one process per
  container. HTMX comes with the first page that refreshes part of itself.
- Postgres 18 and later is the only database. For development, one shared Docker container
  (`docker compose up -d`, on `127.0.0.1:5442`) holds a database per worktree.
- The product has no Node toolchain. Node is on a developer's machine only for the OpenSpec CLI.
- One container image, `fcon`, for every role, from the root `Dockerfile`. Production on one
  machine runs `deploy/compose.yaml`: the upgrade step, the server and Caddy, with Postgres
  outside; the guide is `docs/deploy.md` (ADR 0015).

**Front end** (owner, 13-Nov-2026):

- Pages are server-rendered first. A part of a page is refreshed through HTMX attributes.
  Hand-written JavaScript is kept to what a browser test pins down; the rules are in the
  `test-driven-development` skill, `references/python.md` § JavaScript in a server-rendered page.
- React comes in only when a screen needs interaction that a browser test cannot pin down
  cheaply: branching logic in the browser, state kept across interactions, data reshaped there.
  Then React is added for that screen alone, mounted inside a server-rendered page; the
  dashboard is not converted.
- Adding it is an OpenSpec change with an ADR, because it brings a Node toolchain into the
  product. From then on the client's code follows the JavaScript column of the
  `outside-in-tdd` skill's § Reconcile and the server's the Python column; the acceptance suite
  stays `stack: python` and gets a second service in `support/stack.py`; and the promise that
  pages work with JavaScript off is withdrawn for that screen by a MODIFIED requirement.
- To keep that step cheap: what a page shows is computed in Python functions the template only
  prints; the services behind the pages are separate from the HTML routes, so a JSON route can
  call the same service; and everything the acceptance suite knows about the UI stays inside
  page objects.

**Tooling defaults, never asked**, added to those of the `change-modes` skill (§ Defaults): ruff to lint and
format (the defaults plus `S`, `B`, `I`, `UP`), pyright in strict mode, vulture, deptry, pytest
for inner tests with 100% coverage, behave with Playwright for the acceptance suite
(`stack: python`), `uv run` for every command. The end-of-change checks are the Python column of
the table in the `outside-in-tdd` skill, § Reconcile, and CI runs them (`.github/workflows/`).
deptry reads one package's `pyproject.toml`: run it from each package's directory,
`uv run --directory packages/<package> deptry .`. Relaxed until the M1 release (#5): mutmut runs
weekly as a report, the Windows and macOS tests do not block, Dependabot proposes monthly.

**Conventions** (one line each; the reasons are in [`adr/`](adr/)):

1. Settings come only from `FCON_*` environment variables, and from `.env` in development.
2. Every command reports problems through the error helper in `fcon-cli`: what is wrong and
   what to do, never a password, never a traceback for an expected problem.
3. One logger: text on a terminal, one JSON object per line elsewhere.
4. Templates have no inline `<script>` and no `style=""`: the content policy refuses them.
5. Redirects are relative.
6. The flow library never imports the server or the command line.
7. Database calls are sync, through psycopg, with plain SQL in the store layer.
8. Tests that need a database are marked as such, and never skip.
9. Examples and names are generic: no real organisation, customer, vendor system or site.
10. Technical names use `fcon`: the packages, imports, the command, `FCON_*` settings, and
    anything new such as the database schema, loggers, cookies and images. Text people read says
    Feather Connect.
11. Every table, call, token, session, log line, audit record and job carries the tenant; code
    takes it only from the request's or job's context, never from an address or a request body.
12. Every table has `created_at` and `created_by`; a table whose rows change also has
    `updated_at`, `updated_by` and `row_version`. Times are `timestamptz` in UTC, from the clock
    object; SQL never calls `now()`. "By" is `user:<id>`, `token:<id>` or `system:<name>`. The
    store fills them from the context; no query sets them by hand, and no trigger does.
13. Concurrency: an edit applies only at the row version it read, else "changed by someone else"
    (409 in the API); work is claimed with `FOR UPDATE SKIP LOCKED` and an expiring lease; what
    must happen once is a unique constraint written with `ON CONFLICT DO NOTHING`; default
    isolation, short transactions, never one open across a call to another system, rows locked
    tenant then id.
14. Tables: in the schema `fcon`, always named in full, singular snake_case; `_id`, `_at`, `is_`;
    key `(tenant_id, id)` with ids from `new_id()`; a reference carries the tenant; every
    reference is indexed and every index starts with `tenant_id`; fixed sets are text with a
    `CHECK`, never an enum; `text`, not `varchar(n)`; text keys `collate pg_c_utf8`, lists for
    people sorted `collate "und-x-icu"` in the query only; no "deleted" flag; long lists paged by
    key, never `OFFSET`; rows written through the store's helpers, which write the audit record.
15. Migrations expand, then contract: a migration only adds (tables, columns that are optional or
    have a default); removing or renaming waits for a later release; a migration that ran is never
    edited. The code review checks every migration against this.
16. Flow and package code never reaches the store or gets the product's database address; only
    the server and the worker do.

**Who decides** (owner, 23-Nov-2026; the full table is in [`docs/process.md`](docs/process.md)).
The owner decides scope, the agreed design, the proposal and specs, every ADR, and the merge. The
developer running a build approves its design and tasks. A product question the agreed design does
not answer goes to the owner as a comment on the issue, never decided in code, and its answer is
added to the issue's design.

**Worktrees.** The ports come from the issue number `n`: development `18000 + n`, acceptance
`19000 + n` (issue 4: 18004 and 19004); the main checkout keeps 8080 and 8030. Each worktree has
its own database `feather_issue_<n>` in the shared container. `uv run scripts/worktree_env.py <n>`
writes the worktree's `.env` (both ports, the database address, and a random `FCON_SECRET_KEY`
when it has none; other lines are kept) and creates the database; `--drop` removes it when the
worktree goes. Nobody can sign in to a new database: `uv run fcon users add admin` makes its
first user, an administrator, with the password typed (later users' passwords work once). The
acceptance suite makes its own users and keys.

**Windows.** Four things differ on a Windows machine:

- The skills under `.claude/skills/` are symbolic links. They work only with Developer Mode on
  and `git config core.symlinks true` set before the checkout; without both, each link is a
  one-line text file and its skill is missing from the session. If a skill named in this
  file or in `CLAUDE.md` is not in your skill list, read `.agents/skills/<name>/SKILL.md` and follow it.
- Tools installed with npm are called with `.cmd` in PowerShell (`openspec.cmd`) unless the
  user's execution policy allows scripts.
- mutmut does not run on Windows itself: run it in CI, WSL or a Linux container.
- Stopping `uv run` by its PID can leave its Python child holding the port: stop the whole tree,
  `taskkill /T /PID <pid>`.
