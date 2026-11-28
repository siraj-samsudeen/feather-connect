# ADR Review Manifest

- Status: completed
- Review date: 2026-11-28

## Review Summary

Issue #31 point 2's choice that is hard to undo once versions and deliveries point to it (a
stable entry per name, a copy per package version, settings beside it) is one repository-level
ADR; the rest of the design's decisions are in `design.md`.

## In-Force ADRs Reviewed

- [0002 Three packages](../../../adr/0002-three-packages.md): the catalog lives in `fcon-server`; the flow library never imports it
- [0005 psycopg, sync, plain SQL](../../../adr/0005-psycopg-sync-plain-sql.md)
- [0006 Settings from environment variables](../../../adr/0006-settings-from-environment-variables.md): `FCON_PROTECTED`; operator settings are data, not environment settings
- [0008 fcon as the technical name](../../../adr/0008-fcon-technical-names.md): `fcon catalog`, `fcon settings`
- [0009 Tenants on every row](../../../adr/0009-tenants-on-every-row.md): an environment is a deployment, so "per environment" is the database itself; every new row carries the tenant
- [0010 Database upgrades](../../../adr/0010-database-upgrades.md): one expand-only migration
- [0011 The store in fcon-server](../../../adr/0011-store-in-fcon-server.md)
- [0012 UUIDv7 ids](../../../adr/0012-uuidv7-ids.md)
- [0013 Concurrency](../../../adr/0013-concurrency.md): a package version recorded once (`ON CONFLICT DO NOTHING`); recording serialised per package; settings rows locked before a change
- [0014 The audit log and two roles](../../../adr/0014-audit-log-and-two-roles.md): every catalog and settings write audited, with the reason
- [0016 Users, roles and one rights check](../../../adr/0016-users-roles-and-one-rights-check.md): three new actions in the one rights table

None is superseded by this change.

## New Durable ADRs Created

- [0019 The catalog is written from the code, one stable entry per name; operator settings sit beside it](../../../adr/0019-catalog-and-operator-settings.md)
