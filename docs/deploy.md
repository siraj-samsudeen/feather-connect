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

Fill in `deploy/.env`: the site's name, the two database addresses and the secret key
(`openssl rand -hex 32` makes one). It holds passwords: never put it in git (git ignores it
already). Then, from the checkout's root:

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

### The first administrator

Nobody can sign in until there is a user. Make the first administrator one of two ways:

- **From the command line**, once the setup is up. It asks for the password twice; the first
  user keeps the password typed, and is always an administrator:

  ```sh
  docker compose -f deploy/compose.yaml exec server fcon users add admin@example.com
  ```

  The same works on a setup that is not running: `docker compose -f deploy/compose.yaml run
  --rm server users add admin@example.com` (the image's command is `fcon` already).
- **From the settings:** set `FCON_FIRST_ADMIN=admin@example.com` in `deploy/.env` before the
  first start. When the server starts with no users, it makes that user an administrator with a
  one-time password and writes the password in its log, once:
  `docker compose -f deploy/compose.yaml logs server`. Sign in with it and choose your own.
  Once there is a user, the setting does nothing; remove it.

Then add the others from the command line: `fcon users add <name> --role operator` (or
`viewer`, `developer`, `--admin`). Their password works once: they choose their own at the
first sign-in. `fcon users list`, `disable`, `enable` and `set-role` do the rest.

### The visitor's address

The server records each visitor's address with every sign-in, and slows guessing by it. Behind
Caddy, the address the server sees is Caddy's; the visitor's own is in the `X-Forwarded-For`
header Caddy adds. The server believes that header only from the proxies `FCON_TRUSTED_PROXIES`
names.

`deploy/compose.yaml` sets it to Docker's private ranges, `172.16.0.0/12,192.168.0.0/16,10.0.0.0/8`,
because Caddy's address on the setup's network is not fixed. That is safe in this setup: the
server opens no port on the machine, so only the setup's containers and the machine itself reach
it, and Caddy replaces any `X-Forwarded-For` a visitor sends with the one address it saw. If you
give Docker other address pools, set `FCON_TRUSTED_PROXIES` in `deploy/.env` to cover them.

Where Docker hides the visitor's address from Caddy (Docker Desktop, or IPv6 without
`ip6tables`), every visitor arrives from one address, so the slowing by address slows everyone
at once. A Linux machine taking visitors over IPv4 is fine.

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
- **https** comes from the host's proxy. The product itself speaks plain http. The session
  cookie is always marked secure, unless the product listens on its own machine only.
- **The secret key.** Set `FCON_SECRET_KEY` to at least 32 random characters
  (`openssl rand -hex 32`), as a secret variable of the host. The product does not start
  without it.
- **The visitor's address.** Set `FCON_TRUSTED_PROXIES` to the addresses or ranges the host's
  proxy connects from, if the host says. If it does not, and only the host's proxy can reach the
  container (no public port of its own), set `*`: then the server believes whoever connects, but
  only the last address in `X-Forwarded-For`, the one the proxy saw. Never set `*` where anyone
  else can reach the container. Unset, the server records the proxy's address, and its log
  warns once: `warning: requests carry X-Forwarded-For, but no proxy is trusted; set
  FCON_TRUSTED_PROXIES.`
- **The first administrator.** Set `FCON_FIRST_ADMIN` before the first deploy, and read the
  one-time password in the product's log; or run `fcon users add <name>` in the host's shell for
  the service, if it has one.
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
| `FCON_SECRET_KEY` | Both | At least 32 random characters, signing the sign-in form. Required. Make one with `openssl rand -hex 32`. |
| `FCON_SECRET_KEY_PREVIOUS` | Both, while changing the key | The old key, so sign-in forms already open still work. Remove it a day later. |
| `FCON_FIRST_ADMIN` | Either | A user name: on a start with no users, made an administrator with a one-time password, written in the log once. |
| `FCON_TRUSTED_PROXIES` | Both | The proxies whose `X-Forwarded-For` is believed: addresses or ranges, comma-separated, or `*` where only the proxy can reach the server. Unset: none. The setup on one machine sets Docker's private ranges. |
| `FCON_PROTECTED` | Either | `on` marks a protected environment: every change to an operator setting needs a reason (`--reason`), and a change without one is refused and recorded. Default `off`; the one-machine template sets it `on`. |
| `FCON_ENVIRONMENT` | Either | The install's name, shown on every page, such as `production` or `staging`. Default `development`. |
| `FCON_DATABASE_POOL_SIZE` | Either | The product's connections to the database. Default 5. |
| `FCON_DATABASE_PREPARE` | Either | `off` behind a connection pooler that cannot keep prepared statements. Default `on`. |

**Changing the secret key:** set the new one as `FCON_SECRET_KEY` and the old one as
`FCON_SECRET_KEY_PREVIOUS`, restart, and remove the old one a day later. Signed-in users stay
signed in: sessions are kept in the database, not signed with the key.

## Not yet

- Backups are the database administrator's: the setup holds no data.
