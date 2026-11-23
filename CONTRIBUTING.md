# Contributing to Feather Connect

How a developer sets up a machine and takes up work, alone or beside others. The process itself
lives in [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) and the skills under
[`.agents/skills/`](.agents/skills/); this page is the way in. How a change moves from issue to
merge, and who does what, mapped to the roles of a usual team: [`docs/process.md`](docs/process.md).

## Set up your machine, once

| Tool | What for |
|---|---|
| Git, and the GitHub CLI `gh` signed in (`gh auth login`) | The code, issues and PRs |
| [uv](https://docs.astral.sh/uv/) | Python 3.14 (uv fetches it) and every command, as `uv run …` |
| Docker (Docker Desktop, or Docker Engine on Linux) | The development database, Postgres 18 |
| Node.js and the OpenSpec CLI: `npm install -g @fission-ai/openspec@2.0.0` | The spec workflow. Node is a developer tool here; the product has none |
| An AI coding agent | Claude Code reads `CLAUDE.md`; Codex, OpenCode, Cursor and other tools read `AGENTS.md` |
| The Codex CLI, optional | Local reviews: `codex review --base main` |

Set your git name and email (`git config --global user.name …` and `user.email …`). To keep your
address out of the history, use your GitHub no-reply address.

On Windows, before you clone: turn on Developer Mode and run
`git config --global core.symlinks true`. The skills under `.claude/skills/` are symbolic links,
and without both each one checks out as a one-line text file. The other Windows notes are in
`AGENTS.md` § Project.

## Get the code running

```sh
git clone -c core.symlinks=true https://github.com/siraj-samsudeen/feather-connect.git
cd feather-connect
docker compose up -d            # Postgres 18 on 127.0.0.1:5442, shared by every worktree
cp .env.example .env            # PowerShell: Copy-Item .env.example .env
uv sync
uv run fcon db upgrade          # brings the database's tables up to this version
uv run pytest                   # the inner tests, which must cover 100% of the code
uv run --project acceptance-tests playwright install chromium     # once per machine
uv run --project acceptance-tests python acceptance-tests/run_acceptance.py
uv run fcon server           # then open http://127.0.0.1:8080
```

After pulling a change that adds a migration, run `uv run fcon db upgrade` again;
`uv run fcon db status` lists the upgrades applied, with when they ran, and those waiting, and
changes nothing. A migration that ran is never edited: add a new one (CI's checks refuse an edit).

When a command can't run, it says what is wrong and what to do. How the acceptance suite works,
and how to watch it in a browser: [`acceptance-tests/README.md`](acceptance-tests/README.md).

## Take up an issue

1. **Pick one that is ready:** open, assigned to nobody, with no open blockers (GitHub shows
   "Blocked by"), and with an "Agreed design" section. Every issue carries a rating: red, yellow,
   green or chore (the `issue-workflow` skill).
2. **Assign it to yourself first**, so nobody else takes it: `gh issue edit <n> --add-assignee @me`.
   One issue at a time per worker.
3. **Make its worktree**, from your main checkout, named after the issue and its OpenSpec change:

   ```sh
   git worktree add ../feather-connect-issue-<n> -b issue-<n>-<change-name> main
   cd ../feather-connect-issue-<n>
   uv run scripts/worktree_env.py <n>   # .env: ports 18000+n and 19000+n, database feather_issue_<n>
   ```

   It creates the worktree's database and upgrades it; run it again, or `uv run fcon db upgrade`,
   after bringing in a migration.

4. **Start your agent in the worktree** and tell it: "work on issue <n> in build mode" (or
   learning mode while you are new to the code). Product questions go to the owner on the issue;
   who decides what is in [`docs/process.md`](docs/process.md) § Working as a developer with AI. The other
   modes are autopilot and learning (the `change-modes` skill), and you can switch at any time. The
   change then goes: planning artifacts, one commit each after you approve it; the PR; the build;
   the checks; the review videos; the archive.
5. **After the merge:** `uv run scripts/worktree_env.py <n> --drop` removes the worktree's database,
   then `git worktree remove ../feather-connect-issue-<n>`.

## Designs, reviews and merging

- **Designs.** An issue's design is agreed with the product owner before work starts: one question
  per message, with mockups for anything a person sees, until the design is a numbered checklist in
  the issue (the `issue-workflow` skill).
- **Reviews.** A change a person can see takes the UI route: an independent verifier checks the
  real pages against that checklist. A code review covers what testing can't show: security,
  permissions, data and server logic. Docs, cosmetic changes and very minor fixes get no review.
  The rules and the triage of findings: `AGENTS.md` § Review guidelines.
- **Merging.** A change's PR merges when the required checks pass and the product owner approves
  it. A docs or chore PR needs one other developer's approval. Changes merge with a merge commit,
  never a squash, so their red, green and refactor steps survive.
- **Required checks on `main`:** Checks, Tests, Acceptance and Specs. The Windows and macOS tests
  and mutation testing report without blocking until the M1 release (issue #5).

## Working beside other people

- **One change per capability at a time.** Two changes to the same `openspec/specs/<capability>`
  collide when they are archived.
- **ADR numbers.** Take the next free number in `adr/`. If `main` takes it first, renumber yours
  when you bring `main` in.
- **Lock files.** Never merge `uv.lock` or `acceptance-tests/uv.lock` by hand: after bringing in
  `main`, run `uv lock` (and `uv lock --project acceptance-tests`).
- **Bringing in `main`.** Once a PR is open, merge `main` into your branch
  (`git merge origin/main`) rather than rebasing, so nobody has to force-push.
- **The shared database.** One container serves every worktree on a machine. Never run
  `docker compose down -v`: it deletes every worktree's database. Tests never stop it.

## Rules every change keeps

The conventions in `AGENTS.md` § Project apply to every change. Among them: settings come only from
`FCON_*` environment variables; templates have no inline scripts or styles; examples and names
are generic, never a real organisation, customer, vendor system or site. Never commit a secret:
`.env` is git-ignored.

## Where things are

| What | Where |
|---|---|
| What the product must do, by milestone | [`docs/requirements.md`](docs/requirements.md) |
| What it does today | [`openspec/specs/`](openspec/specs/) |
| Why it is built this way | [`adr/`](adr/) |
| How a change moves, step by step and role by role | [`docs/process.md`](docs/process.md) |
| How the team works | [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md), [`.agents/skills/`](.agents/skills/) |
| The acceptance suite | [`acceptance-tests/README.md`](acceptance-tests/README.md) |

A code of conduct, a private way to report a security problem, and named owners for
security-sensitive code come with requirement R15.8.
