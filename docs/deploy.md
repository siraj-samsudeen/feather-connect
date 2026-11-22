# Deploying Feather Connect

Feather Connect runs from one container image, `fcon`, in two ways: on one machine of your own
with Docker Compose, or on a cloud host that runs containers. The reasons are in
[ADR 0015](../adr/0015-container-setup.md).

In the examples, the site is `connect.example.com` and the Postgres server is
`pg.example.internal`. Put your own names in their place.

## What you need, both ways

- **The image `fcon`.** Until releases publish it, it is built from this repository: the
  `Dockerfile` at the root. The same image runs the upgrade (`fcon db upgrade`) and the product
  (`fcon server`, its default command).
- **A Postgres 18 server.** Feather Connect needs Postgres 18 or later
  ([ADR 0004](../adr/0004-postgres-18-only.md)). A host's one-click Postgres may default to an
  older version: choose 18. On an older server the product starts but is not ready, and its log
  says which version it found.

### The administrator's one-time SQL

The database administrator runs this once on the Postgres server, as a user who may create users
and databases:

```sql
CREATE ROLE fcon LOGIN PASSWORD '<owner-password>';
CREATE ROLE fcon_app LOGIN PASSWORD '<app-password>';
CREATE DATABASE fcon OWNER fcon;
```

- `fcon` is the owner user: the upgrade signs in as it and creates the schema `fcon` and its
  tables.
- `fcon_app` is the app user: the product signs in as it.
- Nothing else is needed. The first `fcon db upgrade` creates the schema and grants the app user
  its rights: to use the schema, and to read and write its tables, except the audit log, which it
  may only read and add to. The upgrade grants them again each time it runs.
- Postgres lets every user connect to a new database. If your server has taken that right away
  from everyone (`REVOKE CONNECT ... FROM PUBLIC`), also run
  `GRANT CONNECT ON DATABASE fcon TO fcon_app;`.
- An administrator who is not a superuser (often so on a managed Postgres) must be a member of
  `fcon` to make it the database's owner: run `GRANT fcon TO <administrator>;` before
  `CREATE DATABASE`.

Passwords: long and random. Hex is suggested, for example `openssl rand -hex 32`, because it can
go into a database address as it is. Any other password must be percent-escaped in an address
(`@` becomes `%40`, `/` becomes `%2F`, and so on). In `deploy/.env`, Docker Compose also reads `$`
as the start of a variable: write a `$` in a password as `$$`.

The two database addresses are then:

```text
postgresql://fcon:<owner-password>@pg.example.internal:5432/fcon
postgresql://fcon_app:<app-password>@pg.example.internal:5432/fcon
```

## One machine

`deploy/compose.yaml` runs three containers:

- `migrate` runs `fcon db upgrade` once, as the owner user, and stops.
- `server` runs `fcon server`, as the app user. It starts only when `migrate` succeeded.
- `caddy` serves the site over https, with a certificate it gets and renews, and sends plain http
  on to https. It starts when `server` is healthy. Only Caddy opens ports on the machine.

Postgres is not part of the setup, and the setup holds no data.

### Before you start

- Docker with Compose, on Linux.
- The site's name (`connect.example.com`) points at the machine.
- Ports 80 and 443 reach the machine from the internet, so Caddy can get the certificate.
- The machine can reach the Postgres server.

### Start it

```sh
git clone https://github.com/siraj-samsudeen/feather-connect.git
cd feather-connect
cp deploy/.env.example deploy/.env
```

Fill in `deploy/.env`: the site's name and the two database addresses. It holds passwords: never
put it in git (git ignores it already). Then, from the checkout's root:

```sh
docker compose -f deploy/compose.yaml up -d --build
```

What happens, in order. Each step waits for the one before it:

1. Docker builds the image `fcon` from the checkout.
2. `migrate` upgrades the database. If it fails, nothing more starts.
3. `server` starts and becomes healthy.
4. `caddy` starts, gets the certificate and serves the site.

A missing setting stops the command at once, with the name of the setting to set.

Check it: `https://connect.example.com/readyz` answers 200, with the status `ready`, once the
product can use its database.

### Logs

```sh
docker compose -f deploy/compose.yaml ps -a
docker compose -f deploy/compose.yaml logs migrate
docker compose -f deploy/compose.yaml logs server
docker compose -f deploy/compose.yaml logs caddy
```

- `migrate` prints `applied <file>` for each upgrade and ends with
  `the database is up to date: N upgrades applied.`, or prints
  `the database was already up to date.`
- `server` warns that it can be reached from other machines: that is expected, since it listens
  on the setup's own network, behind Caddy.

### A new version

```sh
git pull
docker compose -f deploy/compose.yaml build
docker compose -f deploy/compose.yaml run --rm migrate
docker compose -f deploy/compose.yaml up -d
```

The third command upgrades the database while the old server keeps serving: upgrades only add,
so the old version keeps working on the upgraded database. If it fails, it says why, and nothing
else has changed: fix the cause, often the database's address or its server, and run it again. An
upgrade that failed leaves the upgrades before it in place, and the next run carries on from
there. The last command then replaces the server; its own upgrade step finds nothing left to do.

Running only `up -d --build` also upgrades first, but Compose stops the old server before the
upgrade runs: if the upgrade then fails (`service "migrate" didn't complete successfully`), the
new server does not start, and the site answers with an error until the upgrade succeeds.

### A Postgres on the same machine

The containers reach the machine itself as `host.docker.internal`:

```text
postgresql://fcon_app:<app-password>@host.docker.internal:5432/fcon
```

Postgres must listen on Docker's bridge, not only on `localhost`, and allow Docker's networks:

- `postgresql.conf`: `listen_addresses = 'localhost,172.17.0.1'` (the bridge's address; see
  `ip addr show docker0`).
- `pg_hba.conf`: `host fcon fcon,fcon_app 172.16.0.0/12 scram-sha-256` (the setup gets a network
  of its own in that range).

Then reload Postgres.

## A cloud host that runs containers

The same image runs twice per deploy: once for the upgrade, then as the product.

- **The image.** Let the host build it from this repository's `Dockerfile`, or build it yourself
  (`docker build -t fcon .`) and push it to the host's registry.
- **The database.** A Postgres 18 server, with the administrator's one-time SQL run on it. If the
  host offers its own Postgres, choose version 18.
- **The settings.** `FCON_DATABASE_URL`, the app user's address. `FCON_MIGRATION_DATABASE_URL`,
  the owner user's address, is needed only by the pre-deploy step; if the host lets you set a
  variable for that step alone, keep it there. The pre-deploy step needs both: it upgrades as the
  owner and grants its rights to the user of `FCON_DATABASE_URL`.
- **The pre-deploy command:** `fcon db upgrade`. If it fails, the deploy stops there, and its
  log says why.
- **The start command:** leave it empty. The image's default is `fcon server`.
- **The port.** The product listens on the port the host gives in `PORT`. To choose it yourself,
  set `FCON_PORT`.
- **The health check:** the path `/readyz`, which answers 200 when the product can use its
  database. For a liveness check, use `/healthz`, which answers while the process runs.
- **https** comes from the host's proxy. The product itself speaks plain http.
- **A host that reaches containers over IPv6 only:** set `FCON_HOST=::`.

## The settings

| Name | Where | What |
|---|---|---|
| `FCON_DOMAIN` | One machine (`deploy/.env`) | The site's name, such as `connect.example.com`. Caddy gets its certificate. |
| `FCON_DATABASE_URL` | Both | The app user's database address. Required. |
| `FCON_MIGRATION_DATABASE_URL` | Both, for the upgrade only | The owner user's database address. Unset: the upgrade uses `FCON_DATABASE_URL`. |
| `PORT` | A cloud host | The port to listen on, given by the host. Default 8080. |
| `FCON_PORT` | Either | The port to listen on; wins over `PORT`. |
| `FCON_HOST` | Either | The address to listen on. The image sets `0.0.0.0`; `::` for IPv6. |
| `FCON_LOG_FORMAT` | Either | `text` or `json`. Unset: text on a terminal, one JSON object per line elsewhere. |
| `FCON_DATABASE_POOL_SIZE` | Either | The product's connections to the database. Default 5. |
| `FCON_DATABASE_PREPARE` | Either | `off` behind a connection pooler that cannot keep prepared statements. Default `on`. |

## Not yet

- Backups are the database administrator's: the setup holds no data.
- A secret key for sessions comes with sign-in (#16).
