# Python Stack - behave

For `stack: python` in `openspec/config.yaml`. Read the skill's `SKILL.md` first for the spec format and runner invariants, plus [../EXTRACTION.md](../EXTRACTION.md) and [../COMPOSITION.md](../COMPOSITION.md) — the two normative contracts this pack implements.

Requires `behave>=1.2.7` for Gherkin v6 `Rule:` support. Checked on 13-Nov-2026 with behave 1.3.3, behave-html-formatter 0.9.10 and Playwright 1.65.1, on Python 3.15 and Windows 11.

## Files To Copy

Copy into `acceptance-tests/` at the repo root. Destination filenames are load-bearing.

| Source | Destination | Why the name is fixed |
| --- | --- | --- |
| `python/extract_gherkin.py` | `extract_gherkin.py` | imported by `run_acceptance.py` |
| `python/openspec_effective_spec.py` | `openspec_effective_spec.py` | imported by `run_acceptance.py` |
| `python/run_acceptance.py` | `run_acceptance.py` | documented single entry point |
| `python/behave.ini` | `behave.ini` | behave discovers its config by this name |
| `python/environment.py` | `environment.py` | behave loads hooks from this name at the base dir |
| `python/pyproject.toml` | `pyproject.toml` | makes `acceptance-tests/` a project of its own (uv) |

Then copy these starting points into `acceptance-tests/support/` and fill in the lines marked `PROJECT:`. They are not verbatim copies; they are the patterns every project needs:

| Source | Destination | What it gives |
| --- | --- | --- |
| `python/support/stack.py` | `support/stack.py` | Boots the app on its own database and port (`ACCEPTANCE_PORT`), so it runs beside the dev server and other worktrees; refuses to start, naming the port, while another run holds it; stops the app and its child processes on Windows, macOS and Linux |
| `python/support/auth.py` | `support/auth.py` | People start signed in: a Playwright storage state from the same request the sign-in form makes, hidden CSRF field included, so the form is typed only in sign-in scenarios; one signed-in session per run for setup |
| `python/support/world.py` | `support/world.py` | The World: one browser context per person, desktop at the answers' `ui_verifier_width`, `use_phone()`, `without_javascript()`, a screenshot of every failed scenario, and the watching and debugging switches below |
| `python/support/captions.py` | `support/captions.py` | `VIDEO=1` only: each step's text as a caption over every open page, a hold after each Then, and a pulsing dot so Playwright keeps recording. Copy verbatim |
| `python/scripts/video_journey.py` | `scripts/video_journey.py` | Joins the last `VIDEO=1` run's clips into one `reports/videos/journey.mp4`. Copy verbatim |

`acceptance-tests/.gitignore`: `.venv/`, `__pycache__/`, `.extracted/`, `reports/`.

## Required Layout

```text
acceptance-tests/
  run_acceptance.py      environment.py     behave.ini      pyproject.toml
  extract_gherkin.py     openspec_effective_spec.py
  steps/                 # step definitions
  pages/                 # page objects
  support/               # stack.py, auth.py, world.py, captions.py
  scripts/               # video_journey.py
  .extracted/  reports/  # generated, gitignored
```

`steps/` and `environment.py` must sit at the `acceptance-tests/` root, not under a `features/` directory. `steps/`, `pages/` and `support/` import each other by those names (`from pages.signup_page import SignupPage`); the wrapper puts `acceptance-tests/` on the import path.

## Project Setup

`acceptance-tests/` is an independent project with its own `pyproject.toml` and environment. It drives the running app from outside and never imports the app's code, so the app's dependencies stay out of it. Its hooks boot the application before the suite and shut it down after, so the suite runs with one command.

```sh
uv sync --project acceptance-tests
uv run --project acceptance-tests playwright install chromium     # once per machine
```

If the repo root is a uv workspace, leave `acceptance-tests` out of its members.

## Commands

From the repo root:

```sh
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py                    # effective spec
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py --specs            # source of truth only
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py --print-locations  # show resolved composition
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py --dry-run          # passthrough to behave
```

Always go through the wrapper. behave parses feature files before `environment.py`'s `before_all` hook fires, so extraction cannot live in a hook. `before_all` refuses to start unless the wrapper set `OPENSPEC_ACCEPTANCE`. The wrapper's exit code is behave's: 0 only when every scenario passed.

## Exclusion

The contract is that superseded scenarios must not reach the runner and must not appear as skipped. behave's `spec.feature:12` selects at runtime and reports unselected scenarios as skipped, so this pack prunes superseded `Rule:` blocks out of the generated `.extracted/` tree and passes whole files to behave.

Pruning is not a spec edit. `.extracted/` is generated, gitignored, and rebuilt every run. Blanking rather than deleting keeps line fidelity.

## Verification

```sh
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py --print-locations
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py --dry-run
```

Locations must show only `.extracted/` entries and nothing under `changes/archive/`. Compare dry-run scenario count and names against the JS stack on the same specs.

## Server-Rendered Pages

A server-rendered app (FastAPI or Django with templates, with or without HTMX) differs from a single-page app in four ways the support files already allow for:

- **Signing in is a form post, not a JSON call.** `support/auth.py` loads the sign-in page, copies the form's hidden fields (the CSRF token) and posts the form. A refused sign-in often answers 200 with the form again, so it checks that the answer left the sign-in page, not the status. Setup that posts one of the app's own forms needs that form's hidden fields too: `auth.form_fields(session, path)`.
- **Almost every step loads a new document.** Playwright waits for the navigation a click starts; wait for what the next page shows (`expect(...)`, a locator), never for a fixed time. An HTMX swap is not a navigation: wait for the swapped content the same way.
- **Pages can promise to work with JavaScript off.** `world.without_javascript()` in a Given makes the scenario's pages run without it, so the promise is one scenario in the product-wide spec, not a separate suite.
- **One process serves everything.** `support/stack.py` has one service and one port. If a separate client (a React dev server) is added later, add a second service and point `BASE_URL` at it; specs, steps and page-object method names stay, and only the page objects' insides change.

Drive pages by what a person sees, in this order: role and name (`get_by_role("button", name=...)`), label (`get_by_label(...)`), text. A selector on a class or an id is the last resort, and lives only in a page object.

## Watching And Debugging

For a person at their own screen; agents and CI set none of these, and browser checks run headless. Videos are never recorded by default: a person asks for a `VIDEO=1` run.

| Setting | What it does |
| --- | --- |
| `HEADED=1` | A visible browser, slowed down so each action can be followed. |
| `PWDEBUG=1` | Playwright's Inspector (headed), pausing before each action; no action timeout. |
| `VIDEO=1` | A slowed-down, headless video of every scenario, one per person's browser: `reports/videos/<NN>-<scenario>[-<who>].webm`, numbered in run order. Only a `VIDEO=1` run replaces the videos, so a later plain run leaves the ones to review. A change's scenarios run in its proposal's capability order (COMPOSITION.md), so the videos play the way a person meets the feature. |
| `VIDEO_SLOWMO=<ms>` | How slow a `VIDEO=1` run is, per browser action (default 400). |
| `TRACE=1` | Traces every browser; a failed scenario keeps `reports/traces/<scenario>[-<who>].zip`. On in CI by default. Open one with `uv run --project acceptance-tests playwright show-trace <zip>`. |
| `ACCEPTANCE_PORT=<port>` | The port the run's own app listens on (default 8030); each worktree that runs at the same time needs its own. |

A failed scenario leaves a full-page screenshot in `reports/screenshots/`, also shown under its last step in the HTML report, and the app's own output is in `reports/logs/`.

With `VIDEO=1`, each step's text shows as a caption at the top of every page, and each Then holds for 1.5s so its result can be seen. The caption survives full page loads and a strict Content-Security-Policy (`support/captions.py` says how). To watch a whole change as one video:

```sh
VIDEO=1 uv run --project acceptance-tests python acceptance-tests/run_acceptance.py
uv run --project acceptance-tests python acceptance-tests/scripts/video_journey.py
```

In PowerShell, set the variable first: `$env:VIDEO = "1"`, and remove it after with `Remove-Item Env:VIDEO`.

`video_journey.py` joins the last `VIDEO=1` run's clips, in run order, into `reports/videos/journey.mp4`, each after a 2-second title card "NN · scenario — who"; phone clips are padded onto the desktop canvas (`ui_verifier_width` × 900). It needs a working ffmpeg (`FFMPEG=<path>`, else `ffmpeg` on `PATH`) and says so when there is none.

The owner watches the videos before a change is archived (the `change-modes` skill).

## CI

Run the suite in the job that already has the app's database, after any other browser suite (it boots its own app on its own port), and upload the report, screenshots and traces whatever the result:

```yaml
- name: Run acceptance suite
  run: |
    uv sync --project acceptance-tests
    uv run --project acceptance-tests playwright install --with-deps chromium
    uv run --project acceptance-tests python acceptance-tests/run_acceptance.py

- name: Upload acceptance report
  if: ${{ !cancelled() }}
  uses: actions/upload-artifact@v4
  with:
    name: acceptance-report
    path: acceptance-tests/reports/
    if-no-files-found: ignore
```

If CI picks jobs by changed paths, route `openspec/**/spec.md` and `acceptance-tests/**` (except its `.md` files) to this job: a spec's fenced Gherkin is the suite's source, not prose.

## HTML Report

`behave.ini` pairs formatters with outfiles positionally. `html` must be listed first to claim `reports/behave-report.html`; `progress` gets `-` for stdout.

## Page Object Model

Page objects live in `acceptance-tests/pages/`, one per screen or flow. Each takes the World and asks it for a person's page; it holds the routes, labels and selectors. To read a response that never reaches a browser (a setup request, an email body), parse it with BeautifulSoup; never with regexes over raw HTML. behave's `context` carries the World (`context.world`) and the page objects.

```python
# pages/signup_page.py
class SignupPage:
    def __init__(self, world):
        self.world = world

    def open(self):
        self.page = self.world.signed_out("a visitor")
        self.page.goto("/signup")

    def submit_signup(self, email, password):
        self.page.get_by_label("Email").fill(email)
        self.page.get_by_label("Password").fill(password)
        self.page.get_by_role("button", name="Sign up").click()

    def error_message(self):
        return self.page.get_by_role("alert").inner_text()
```

```python
# steps/signup_steps.py
@when('they submit a valid email and password')
def step_impl(context):
    context.signup_page.submit_signup(
        email='user@example.com',
        password='correct-horse-battery-staple',
    )


@then('an error message is shown')
def step_impl(context):
    assert context.signup_page.error_message()
```
