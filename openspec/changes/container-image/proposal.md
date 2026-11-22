## Why

The product runs only from a checkout. To deploy it, on one machine or on a cloud host that runs
containers, it needs a container image and a production setup (issue 17; R15.2, R15.15, Q-12,
Q-15, and the container part of D-08). It touches no table, so it is built beside the storage
foundation (#12), whose upgrade command it runs.

What people get: an operator runs Feather Connect from one image wherever containers run, giving
it only its settings there. On one machine, one command starts the database, upgrades it, and
serves the dashboard over https, with certificates the proxy gets and renews by itself.

## What Changes

- One container image, `fcon`, for every role: the command decides what runs (`fcon server`,
  `fcon db upgrade`, later `fcon worker`). Python 3.14 slim on Debian 13. It runs as an ordinary
  user, holds no secret and no settings file, and carries no compiler, no uv and no tests. It
  follows the host's `PORT`, and tells the container runtime whether the server is alive.
- Built for both processor families, `linux/amd64` and `linux/arm64` (Q-12).
- CI builds the image for amd64 on every PR and runs a smoke test against Postgres 18: the
  upgrade, then health, readiness and the sign-in page. The arm64 build runs on `main`.
- `deploy/compose.yaml`, production on one machine (R15.2, Q-15): Postgres 18, the server, and
  Caddy, the proxy that encrypts traffic with automatic certificates (R15.15); plus a one-shot
  `migrate` step that upgrades the database and must succeed before the server starts. Settings
  come from a `deploy/.env` the operator writes, never in git.
- `docs/deploy.md`: deploying on one machine with that file, and on a cloud host that runs
  containers, with a managed Postgres 18. It names no host.
- ADR 0015 records the container setup; the catalogue marks the container part of D-08 settled.

## Capabilities

### New Capabilities

- `deployment`: the product runs from its image wherever containers run, given its settings
  there; on one machine, the standard setup upgrades the database before the product starts, and
  serves it only over encrypted connections.

### Modified Capabilities

None.

## Impact

- New files: `Dockerfile`, `.dockerignore`, `deploy/` (the compose file, the proxy's
  configuration, an example `.env`), `docs/deploy.md`, `adr/0015-…`.
- CI: a new image job. Dependabot also watches the image's base and the setup's images.
- The acceptance suite needs Docker for this capability's scenarios: it builds the image and runs
  containers of its own, with their own names and ports, and never touches the shared development
  database.
- `packages/*/src`: unchanged, unless the image needs something the server lacks.
- Waits on #12 (PR #15) for `fcon db upgrade`: the `migrate` step and the smoke test's upgrade are
  wired in once it merges.
- Not in this change: `fcon dev` (R15.1), publishing and signing images and choosing their
  registry (R15.7, D-10), the sizing guide (R15.13), the worker's container (the worker issue),
  and the secret key (#16).
