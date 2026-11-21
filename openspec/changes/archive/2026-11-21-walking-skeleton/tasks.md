## 1. First-time setup — each task is ticked by the red/green pair of the first outer test that needs it

- [x] 1.1 Confirm the acceptance stack: `stack: python` in `openspec/config.yaml`
- [x] 1.2 Set up the application skeleton so the app can boot: the uv workspace (Python 3.14, one lock file), `packages/feather-connect`, `packages/feather-server`, `packages/feather-cli` with the `feather server` command; `compose.yaml` (Postgres 18 on `127.0.0.1:5442`, project name fixed) and `.env.example`
- [x] 1.3 Create `acceptance-tests/` at the repo root as an independent uv project on Python 3.14, left out of the workspace, that creates a throwaway database, starts `feather server` on `ACCEPTANCE_PORT`, waits for readiness, and stops it and drops the database at the end
- [x] 1.4 Copy the Python pack's files verbatim into `acceptance-tests/` (`references/python/SETUP.md` "Files to copy"), so the runner extracts the Gherkin from every `spec.md` under `openspec/` into `acceptance-tests/.extracted/`, excluding `openspec/changes/archive/`; fill in the `PROJECT:` lines of `support/`
- [x] 1.5 Make the single test command always generate an HTML report under `acceptance-tests/reports/`
- [x] 1.6 Gitignore `acceptance-tests/.extracted/` and `acceptance-tests/reports/` (no separate spec lint: the runner's own parse is the check)
- [x] 1.7 Write `acceptance-tests/README.md` with instructions for running the suite and where the HTML report is written

## 2. Step definitions — one task per pending step; each = fails for the right reason → implement → passes → commit

### Logs and health

- [x] 2.1 logs-and-health: Given the product is running with its database — red → green → commit
- [x] 2.2 logs-and-health: When a monitor checks it — red → green → commit
- [x] 2.3 logs-and-health: Then the product answers that it is running — red → green → commit
- [x] 2.4 logs-and-health: And it answers that it is ready to take work — red → green → commit
- [x] 2.5 logs-and-health: Given the product is running — red → green → commit
- [x] 2.6 logs-and-health: But its database cannot be reached — red → green → commit
- [x] 2.7 logs-and-health: But it answers that it is not ready, because its database is unavailable — red → green → commit
- [x] 2.8 logs-and-health: And the answer does not say where the database is — red → green → commit
- [x] 2.9 logs-and-health: When a monitor makes a quick check that asks for no details — red → green → commit
- [x] 2.10 logs-and-health: Then the monitor is told the product is running — red → green → commit

### Users and access

- [x] 2.11 users-and-access: Given the user is not signed in — red → green → commit
- [x] 2.12 users-and-access: When the user opens the dashboard — red → green → commit
- [x] 2.13 users-and-access: Then the sign-in page names the product — red → green → commit
- [x] 2.14 users-and-access: And it asks for the user's name and password, with a button to sign in — red → green → commit
- [x] 2.15 users-and-access: And nobody has been given access yet — red → green → commit
- [x] 2.16 users-and-access: When the user signs in as "alex" with the password "letmein" — red → green → commit
- [x] 2.17 users-and-access: Then the sign-in is refused — red → green → commit
- [x] 2.18 users-and-access: And the user is told the user name or password is wrong, without being told which — red → green → commit
- [x] 2.19 users-and-access: And the page's title says the sign-in failed — red → green → commit

### Dashboard basics

- [x] 2.20 dashboard-basics: And the user has switched scripts off in the browser — red → green → commit
- [x] 2.21 dashboard-basics: Given the user's computer is set to the dark appearance (and light) — red → green → commit
- [x] 2.22 dashboard-basics: When the user opens the sign-in page — red → green → commit
- [x] 2.23 dashboard-basics: Then the page is shown in the dark appearance — red → green → commit
- [x] 2.24 dashboard-basics: When the user opens the sign-in page, a refused sign-in and a page that does not exist — red → green → commit
- [x] 2.25 dashboard-basics: Then an automatic accessibility check finds no problem on any of them — red → green → commit
- [x] 2.29 dashboard-basics: When the user opens the address of run 42, which the dashboard does not have — red → green → commit
- [x] 2.30 dashboard-basics: Then the user is told the page was not found — red → green → commit
- [x] 2.31 dashboard-basics: And the user can go on to the sign-in page from there — red → green → commit

### Local development

- [x] 2.32 local-development: Given no database address has been set — red → green → commit
- [x] 2.33 local-development: When the user starts the server — red → green → commit
- [x] 2.34 local-development: Then the server does not start — red → green → commit
- [x] 2.35 local-development: And it says the database address is missing, and how to set it — red → green → commit
- [x] 2.36 local-development: Given another program is using the server's port (the number it listens on) — red → green → commit
- [x] 2.37 local-development: And it names the port, and says how to choose another — red → green → commit

## 3. What no scenario drives — each still arrives with the test or check that needs it

- [x] 3.1 The import rule: a test that the flow library imports neither the server nor the command line
- [x] 3.2 `scripts/worktree_env.py <n>` writes the worktree's `.env` and creates `feather_issue_<n>`; `--drop` removes it; same on Windows and Linux
- [x] 3.3 CI on GitHub Actions: the checks, tests, acceptance, other-systems and specs jobs of issue 4 point 9; actions pinned by commit id; read-only token; caches
- [x] 3.4 The relaxed checks until M1 (#5): weekly mutmut report on `main`, Windows and macOS not blocking, Dependabot monthly and grouped
- [x] 3.5 `AGENTS.md` § Project: the stack lines confirmed, the worktree ports and database, and the Conventions list of issue 4 point 10

## 4. Completion

- [x] 4.1 Run the full suite: every scenario passes, zero pending/undefined steps, HTML report generated
- [x] 4.2 Run `openspec validate walking-skeleton --type change` before archive
