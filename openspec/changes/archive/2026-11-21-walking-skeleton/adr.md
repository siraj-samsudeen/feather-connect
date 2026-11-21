# ADR Review Manifest

- Status: completed
- Review date: 2026-11-21

## Review Summary

ADR review completed for this change. The seven decisions of issue 4, point 11, are recorded as
repository-level ADRs; the owner approved the seven drafts together, since each was questioned in
points 1 to 10 of the issue. Everything else agreed there is in `design.md`.

## In-Force ADRs Reviewed

- None - `adr/` had no ADRs before this change.

## New Durable ADRs Created

- [0001 Python 3.14 only](../../../adr/0001-python-3-14-only.md) (D-12)
- [0002 Three packages; the flow library imports neither of the others](../../../adr/0002-three-packages.md)
- [0003 Pages rendered on the server: FastAPI, Jinja2 and HTMX under Uvicorn](../../../adr/0003-pages-rendered-on-the-server.md) (D-01)
- [0004 Postgres 18 and later is the only database, with no extensions](../../../adr/0004-postgres-18-only.md) (first half of D-02)
- [0005 psycopg, with sync calls and plain SQL; no object mapper](../../../adr/0005-psycopg-sync-plain-sql.md)
- [0006 Settings come only from environment variables](../../../adr/0006-settings-from-environment-variables.md)
- [0007 A strict content policy on every page from the first one](../../../adr/0007-strict-content-policy.md)

`docs/requirements.md` § 11 marks D-01, D-12 and the first half of D-02 as settled, linking these.
