# 0003. Pages rendered on the server: FastAPI, Jinja2 and HTMX under Uvicorn

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, point 2 (catalogue decision D-01)

## Context and Problem Statement

The catalogue's D-01 asks for the server framework and how pages are rendered and refreshed. The
dashboard's pages must work with JavaScript off (R7.10), on a narrow screen and in light and dark
(R7.11), and the product has no Node toolchain. Turning the whole dashboard into a single-page
application is not planned (catalogue § 12). The project's front-end rule (owner, 13-Nov-2026)
lets React in for one screen only when a browser test cannot pin its interaction down cheaply.

## Considered Options

- FastAPI with Jinja2 templates, HTMX to refresh part of a page, served by Uvicorn with one
  process per container.
- Django with its templates and HTMX.
- A JSON API with a single-page client in React.

## Decision Outcome

Chosen option: "FastAPI, Jinja2, HTMX, Uvicorn", because pages rendered on the server work with
JavaScript off and need no build step, FastAPI's JSON routes and machine-readable API description
(R8.9) come from the same services as the pages, and the project's tests reach the server's code
in the same process. Uvicorn runs one process per container; the host or container runtime
restarts it and adds copies. HTMX is added by the first page that refreshes part of itself.

### Consequences

- Good, because there is no Node toolchain in the product and no client build.
- Good, because what a page shows is computed in Python, where coverage and mutation testing see
  it; templates only print.
- Bad, because FastAPI has no built-in sessions, forms or CSRF tokens: real sign-in has to add
  them (R10.7).
- A screen that needs React later adds it with its own ADR, for that screen alone.
