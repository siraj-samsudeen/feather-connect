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

**Stack.** Lines marked *(proposed)* are to be confirmed by the first change:

- Python, managed with uv. Develop on Python 3.14 *(proposed)*: on 13-Nov-2026 PyYAML had no
  Windows build for 3.15, so installing it there needs a C++ compiler.
- Pages are rendered on the server as HTML. FastAPI, Jinja2 templates and HTMX *(proposed)*.
- Postgres as the only required database, run in Docker for development *(proposed)*.
- The product has no Node toolchain. Node is on a developer's machine only for the OpenSpec CLI.

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
format, pyright for types, pytest for inner tests, behave with Playwright for the acceptance
suite (`stack: python`), `uv run` for every command. The end-of-change checks are the Python
column of the table in the `outside-in-tdd` skill, § Reconcile.

**Worktrees.** Each worktree that runs the acceptance suite at the same time as another sets its
own `ACCEPTANCE_PORT`. The app's own port and database per worktree are added here by the change
that first boots the app.

**Windows.** Three things differ on a Windows machine:

- The skills under `.claude/skills/` are symbolic links. They work only with Developer Mode on
  and `git config core.symlinks true` set before the checkout; without both, each link is a
  one-line text file and its skill is missing from the session. If a skill named in this
  file or in `CLAUDE.md` is not in your skill list, read `.agents/skills/<name>/SKILL.md` and follow it.
- Tools installed with npm are called with `.cmd` in PowerShell (`openspec.cmd`) unless the
  user's execution policy allows scripts.
- mutmut does not run on Windows itself: run it in CI, WSL or a Linux container.
