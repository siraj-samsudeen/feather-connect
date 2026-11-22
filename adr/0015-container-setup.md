# 0015. One container image for every role; on one machine, Compose with Caddy and an outside Postgres

- Status: accepted
- Date: 2026-11-22
- Decision-makers: the project owner
- Decided in: issue #17 (the container part of catalogue decision D-08)

## Context and Problem Statement

The catalogue's D-08 asks how the product is deployed. It runs only from a checkout. It must run
on a cloud host that runs containers and on one machine with no paid licence and no cluster
manager (R15.2, Q-15), in at most four containers, behind a proxy that encrypts traffic, from
images that hold no secret (R15.15), for both common processor families (Q-12). Settings come only
from environment variables (ADR 0006), Postgres 18 is the only database (ADR 0004), and the server
is one Uvicorn process per container (ADR 0003). The database is upgraded by `fcon db upgrade`
before a new version starts (issue 12). Most places that run the product already run a Postgres
server, looked after and backed up by an administrator, and shared by several apps.

## Considered Options

- One image, `fcon`, for every role, the command choosing what runs; on one machine, a Compose
  file with the server, Caddy and a one-shot upgrade step, connected to a Postgres run outside it.
- One image per role (server, upgrade, later worker).
- The same image, with the one-machine setup also running its own Postgres container.
- Alpine or distroless as the base, instead of Debian slim.

## Decision Outcome

Chosen option: "one image for every role, and Compose with Caddy and an outside Postgres",
because one image is one thing to build, test and keep in step, and the setup then differs from a
cloud host only by its proxy. The image is built on `python:3.14-slim-trixie` (Debian 13, like
the Postgres 18 image), pinned by digest; a build stage installs the three packages with uv into a
virtual environment, and the final stage holds only that environment, runs as an ordinary user,
and holds no compiler, no uv, no tests, no settings file and no secret. It sets
`FCON_HOST=0.0.0.0`, follows `PORT`, and checks its own `/healthz`. It is built for `linux/amd64`
and `linux/arm64`. On one machine, `deploy/compose.yaml` runs `fcon db upgrade` once, then the
server, then Caddy, which gets and renews the certificate; only Caddy is reachable from outside.
The administrator makes the database and its two users; the operator gives the two full database
addresses, as on a cloud host. Publishing and signing the image, and its registry, come with
releases (R15.7, the rest of D-10).

### Consequences

- Good, because the same image, settings and pre-deploy command serve a cloud host and one
  machine; only the proxy differs.
- Good, because the setup holds no data: the database, and its backups, stay with whoever already
  looks after Postgres.
- Good, because what reaches the image is an allowlist, so a secret or a test cannot slip in as
  the repo grows.
- Bad, because a machine with no Postgres needs one installed first; the guide says how, and the
  setup reaches one on the same machine.
- Bad, because until releases publish the image, the one-machine setup builds it from a checkout.
- Bad, because base-image fixes wait for Dependabot's monthly proposal, or a pin by hand.
- Rejected: an image per role, more to build and keep in step; a Postgres container in the setup,
  a second database server per app to back up and upgrade; Alpine (musl: slower Python, gaps in
  prebuilt wheels); distroless (no shell to debug, no easy health check).
