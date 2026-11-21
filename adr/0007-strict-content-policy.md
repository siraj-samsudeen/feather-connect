# 0007. A strict content policy on every page from the first one

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, point 6

## Context and Problem Statement

The dashboard needs a policy that refuses inline scripts (R10.7), so that text an attacker gets
onto a page, such as an error message from another system, cannot run. A policy added after many
pages exist finds inline scripts and `style=""` attributes everywhere, and is then loosened to fit
them. The project's acceptance suite injects its accessibility checker and video captions into
pages.

## Considered Options

- A strict policy from the first page: no inline scripts or styles, everything denied unless a
  page needs it.
- Add the policy later, once the pages settle.
- A policy that allows inline code with nonces or hashes.

## Decision Outcome

Chosen option: "strict from the first page", because it is cheapest when there is nothing to undo,
and every later template is written to it. Every response carries a policy that starts from
nothing allowed and opens only what a page uses (this change's design, decision 3), plus no framing
by other sites. Templates have no inline `<script>` and no `style=""`. The tests never loosen it:
axe-core and the captions go in through Playwright's own channel, and an error in the browser's
console fails a scenario.

### Consequences

- Good, because injected text cannot run, from the first page on.
- Good, because a blocked script or style shows up at once as a failing scenario.
- Bad, because every script and style lives in a file, and each new kind of resource is a
  deliberate change to the policy.
