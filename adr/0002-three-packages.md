# 0002. Three packages; the flow library imports neither of the others

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, point 1

## Context and Problem Statement

Flow authors install the flow library and write flows against it; operators run the server; both
use the `feather` command. A flow's environment should not carry the server's web framework and
database driver, and code that flows import should not reach into the server. Splitting a single
package later, once flows and connectors depend on its import paths, is hard.

## Considered Options

- One uv workspace with three packages from the start: `feather-connect` (the flow library,
  `import feather_connect as fc`), `feather-server` (the server and its pages) and `feather-cli`
  (the `feather` command), with one lock file.
- One package, split later when the need shows.
- Separate repositories per package.

## Decision Outcome

Chosen option: "three packages in one workspace", because the boundary is cheapest to draw before
any code depends on it, and one workspace with one lock file keeps them released and tested
together. The flow library never imports the server or the command line, and a test checks it.
feather-cli imports feather-server to start it; feather-server never imports feather-cli.

### Consequences

- Good, because a flow's environment holds only the flow library and what it needs.
- Good, because the import rule is checked by a test, not by memory.
- Bad, because three `pyproject.toml` files and their dependency lists must be kept.
- The end-of-change checks (coverage, types, unused code, dependencies) run over all three.
