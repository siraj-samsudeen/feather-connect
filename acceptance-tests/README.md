# Acceptance tests

The scenarios in `openspec/**/spec.md` run here, against the real product: `feather server`
started as a separate process on its own throwaway database, driven from outside through HTTP and
a browser. This is its own uv project (Python 3.14); it never imports the product's code.

## Run it

From the repo root, with the development database up (`docker compose up -d`):

```sh
ACCEPTANCE_PORT=19004 uv run --project acceptance-tests python acceptance-tests/run_acceptance.py
```

In PowerShell: `$env:ACCEPTANCE_PORT = "19004"; uv run --project acceptance-tests python acceptance-tests/run_acceptance.py`.

- `ACCEPTANCE_PORT` is the port of the run's server (default 8030). Each worktree that runs the
  suite at the same time as another sets its own: `19000 + <issue number>`.
- `ACCEPTANCE_ADMIN_DATABASE_URL` is the Postgres server the run makes its database on (default
  `postgresql://feather:feather@127.0.0.1:5442/postgres`, the development container).
- The first time, install the browser: `uv run --project acceptance-tests playwright install chromium`.

What one run does:

1. Extracts the Gherkin of every `spec.md` into `.extracted/` (rebuilt each run, never edited)
   and composes the effective spec: the source of truth with the active changes applied.
2. Creates an empty database `feather_acceptance_<port>_<random>` and starts
   `uv run feather server` on `ACCEPTANCE_PORT` with `FEATHER_DATABASE_URL` pointing at it, then
   waits until `/readyz` answers 2xx.
3. Runs the scenarios with behave. The outage scenario starts a second server of its own on a free
   port, given a database address where nothing listens, and stops it at the scenario's end.
4. Stops the servers (by process tree) and drops the run's database. The shared database server
   is never stopped.

Other ways to run:

| Command (after `run_acceptance.py`) | What it does |
|---|---|
| `--specs` | The source of truth only (`openspec/specs/`), without the active changes |
| `--print-locations` | Lists the scenarios that would run, runs nothing |
| `-i logs-and-health` | Only the features whose path matches (any behave option passes through) |
| `--dry-run` | Checks that every step has a definition, starts nothing |

`HEADED=1` shows the browser, `PWDEBUG=1` opens Playwright's Inspector, `VIDEO=1` records each
scenario, `TRACE=1` keeps traces of failed scenarios (always on in CI).

## Browser checks

- Chromium at the verifier's width (1280 px); the one narrow-screen scenario uses 320 px
  (`world.use_small_phone()`; `use_phone()` keeps the pack's 375 px).
- The computer's appearance is emulated as `prefers-color-scheme` (`world.use_appearance()`); a
  page is "dark" when its background's relative luminance is below 0.2, "light" above 0.8.
- Any error in the browser's console, or an uncaught error in a page, fails the scenario
  (`environment.py`, after the scenario). The browser's own "Failed to load resource" line for a
  page the scenario opened is left out: the steps check that page's status themselves.

## Reports

- `reports/behave-report.html`: the HTML report, written by every run (a run that stops before the
  first scenario writes a page saying so; the console says why).
- `reports/logs/<service>.log`: what each server printed.
- `reports/screenshots/`, `reports/traces/`, `reports/videos/`: failed scenarios' screenshots and
  traces, and the `VIDEO=1` recordings.

`reports/` and `.extracted/` are git-ignored.

## Layout

| Path | Holds |
|---|---|
| `steps/` | Step definitions: page-object calls and assertions only, no URLs, selectors or texts |
| `pages/` | Page objects: every route, label, selector and expected text (`monitor.py`: `/healthz`, `/readyz`) |
| `pages/sign_in_page.py` | `/`, `/sign-in`, its labels, button, refusal text, and the appearance and phone-width checks |
| `pages/not_found_page.py` | `/runs/42`, the "Page not found" heading and the link on to sign-in |
| `pages/accessibility.py` | axe-core (WCAG 2.1 A and AA), put into the page by Playwright, never by loosening the app's content policy |
| `support/stack.py` | Starts and stops the servers and the run's database |
| `support/world.py` | The scenario's state: its pages, its HTTP client, a server started for it alone |
| `environment.py` | behave's hooks: boot once, one World and the page objects per scenario |
| `run_acceptance.py` | The single entry point: extraction, composition, behave |
