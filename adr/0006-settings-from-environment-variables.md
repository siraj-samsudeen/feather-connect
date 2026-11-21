# 0006. Settings come only from environment variables

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, points 2 and 10

## Context and Problem Statement

The server runs in a container on a cloud host, which passes configuration as environment
variables, and the host's own `PORT`. Developers run several worktrees side by side, each with its
own ports and database. A settings file inside an image would be the same in every environment,
and could carry a secret into the image (R15.15).

## Considered Options

- Environment variables named `FEATHER_*` only, plus a git-ignored `.env` file in development;
  `--host` and `--port` override them for one run.
- A settings file (TOML or YAML) read at start-up, with environment variables overriding it.
- Settings stored in the database.

## Decision Outcome

Chosen option: "`FEATHER_*` environment variables only", because hosts and containers set them
natively, every worktree gets its own values from its `.env`, and nothing about an environment
lives in the image. This change has `FEATHER_HOST`, `FEATHER_PORT` (else the host's `PORT`, else
8080) and `FEATHER_DATABASE_URL`. A `.env` file fills in only what the environment does not set. A
setting that is missing or wrong stops the command with exit code 2 and a message saying what to
do.

### Consequences

- Good, because the same image runs in development, test and production with different values.
- Good, because a mistake is caught at start-up, in one place, with one message.
- Bad, because a long list of settings is awkward as variables; the layered settings of flows
  (R1.9) are a separate matter, decided with them.
