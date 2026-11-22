# ADR Review Manifest

- Status: completed
- Review date: 2026-11-22

## Review Summary

ADR review completed for this change. The container setup of issue 17, point 8, is recorded as
one repository-level ADR; the rest of the design's decisions are in `design.md`.

## In-Force ADRs Reviewed

- [0001 Python 3.14 only](../../../adr/0001-python-3-14-only.md): the image's base
- [0002 Three packages](../../../adr/0002-three-packages.md), names superseded by 0008
- [0003 Pages rendered on the server](../../../adr/0003-pages-rendered-on-the-server.md): one Uvicorn process per container
- [0004 Postgres 18 and later only](../../../adr/0004-postgres-18-only.md): the guide says to choose Postgres 18
- [0005 psycopg, sync, plain SQL](../../../adr/0005-psycopg-sync-plain-sql.md)
- [0006 Settings from environment variables](../../../adr/0006-settings-from-environment-variables.md), names superseded by 0008: nothing about an environment in the image
- [0007 A strict content policy](../../../adr/0007-strict-content-policy.md)
- [0008 fcon as the technical name](../../../adr/0008-fcon-technical-names.md): the image is `fcon`
- In flight on PR #15, not yet on `main`: 0010 (database upgrades) and 0014 (two database roles)

None is superseded by this change.

## New Durable ADRs Created

- [0015 One container image for every role; on one machine, Compose with Caddy and an outside Postgres](../../../adr/0015-container-setup.md) (the container part of D-08)

`docs/requirements.md` § 11 marks the container part of D-08 settled, linking it.
