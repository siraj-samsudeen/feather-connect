# Feather Connect

An open-source integration hub. Flows written in Python move data from one source to many
destinations, and developers, operators and AI agents run, monitor and repair them from one
dashboard.

**Status:** early. The first milestone, M1, is being built; nothing is released yet. What the
product must do, milestone by milestone, is in [`docs/requirements.md`](docs/requirements.md).

## What it will do

- **Flows in plain Python**, built with the `fcon-sdk` library: read from a source, shape the
  data, deliver it to several destinations.
- **One dashboard** to see every flow, run, slice and delivery, find what failed and why, and put
  it right without a command line.
- **Safe by default:** every record carries its tenant, every change is audited, and a failed
  delivery can be retried without sending twice.
- **Runs where containers run:** one image, with Postgres as the only database.

## Built with

| Part | Choice |
|---|---|
| Language | Python 3.14, managed with [uv](https://docs.astral.sh/uv/): three packages, `fcon-sdk`, `fcon-server` and `fcon-cli` |
| Web | FastAPI and Jinja2, pages rendered on the server, HTMX for parts that refresh |
| Database | Postgres 18 or later, plain SQL through psycopg |
| Tests | pytest (100% coverage), behave with Playwright for the acceptance suite |
| Checks | ruff, pyright (strict), vulture, deptry; CI on GitHub Actions |
| Deployment | One container image, `fcon` ([`docs/deploy.md`](docs/deploy.md)) |
| Process | [OpenSpec](https://github.com/Fission-AI/OpenSpec) changes: spec-driven, outside-in TDD |

Why each choice was made: [`adr/`](adr/).

## Run it

```sh
git clone -c core.symlinks=true https://github.com/siraj-samsudeen/feather-connect.git
cd feather-connect
docker compose up -d       # Postgres 18 on 127.0.0.1:5442
cp .env.example .env       # PowerShell: Copy-Item .env.example .env
uv sync
uv run fcon db upgrade
uv run fcon server         # then open http://127.0.0.1:8080
```

The tools to install first, the Windows settings and how to run the tests are in
[`CONTRIBUTING.md`](CONTRIBUTING.md).

## How it is built

Every piece of work goes from a GitHub issue to a merged pull request through the same steps:

1. The **owner** agrees the issue's design, point by point.
2. A **developer**, with an AI agent, plans the change as an OpenSpec proposal, specs, design and
   tasks. The owner approves the proposal and specs.
3. The developer and the agent build it **test first**: failing acceptance scenarios, then unit
   tests and code until they pass.
4. CI runs every check. A **review** by a different model, and for screens an independent
   verifier, checks what tests can't.
5. The **owner** merges.

The full walk-through, with each step mapped to the roles of a usual software team:
[`docs/process.md`](docs/process.md).

## Join the team

The owner makes the product decisions; developers build, each with their own AI agent (Claude
Code, Codex, OpenCode or another) in their own worktree.

1. Set up your machine: [`CONTRIBUTING.md`](CONTRIBUTING.md) § Set up your machine.
2. Pick a ready issue, a small one to start (`good first issue`, green or chore), and assign it to
   yourself.
3. Start your agent in the issue's worktree in **learning mode**, which explains each step, or in
   **build mode** once you know the code.
4. Ask product questions on the issue; decide technical ones yourself.

Who decides what, and a developer's change step by step:
[`docs/process.md`](docs/process.md) § Working as a developer with AI.

## Where things are

| What | Where |
|---|---|
| What the product must do, by milestone | [`docs/requirements.md`](docs/requirements.md) |
| What it does today | [`openspec/specs/`](openspec/specs/) |
| Why it is built this way | [`adr/`](adr/) |
| How work moves, and who decides | [`docs/process.md`](docs/process.md) |
| Setting up, and taking up an issue | [`CONTRIBUTING.md`](CONTRIBUTING.md) |
| Rules every agent and person follows | [`AGENTS.md`](AGENTS.md), [`CLAUDE.md`](CLAUDE.md) |
| The code | [`packages/`](packages/) |
| Deploying it | [`docs/deploy.md`](docs/deploy.md) |

## Licence

MIT: see [`LICENSE`](LICENSE).
