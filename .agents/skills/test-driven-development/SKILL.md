---
name: test-driven-development
description: "Use when implementing a change with test-driven development (TDD): work test-first through focused red-green cycles."
---

# Test-Driven Development

Use the repository's existing test tooling and conventions.

One test, one behaviour, one reason to fail. A test name describes that one
behaviour; never use joiners such as "and", "or", or "etc." to combine
independent outcomes. Multiple assertions are acceptable only when together
they establish that same behaviour.

## Red

- Select one observable behaviour from the requirement.
- Write one test before changing implementation code.
- Run the test and confirm it fails because the behaviour is missing, not because the test is broken.

## Green

- Write only enough implementation code to pass the failing test.
- Run the test, then run the relevant suite.
- Do not add behaviour without first seeing its test fail.

## Refactor

- Refactor only while the relevant suite is green, after completing a red-green slice.
- Refactor either the tests or the implementation in one pass, not both.
- Reuse shared setup, teardown, helpers, and parameterized structure when they clarify intent without combining behaviours.
- Rerun the relevant suite after each refactor pass.

## Patterns and anti-patterns

Read [patterns and anti-patterns](references/best-practices.md) when choosing a test shape, writing examples, or deciding whether cases belong together.

## Properties for logic with many cases

Examples test the cases someone thought of. For logic with many cases (parsing, money and dates,
retries, concurrency, isolation between tenants or users) also write a property: a rule that
holds for every input, checked against hundreds of generated ones (Hypothesis in Python,
fast-check in JavaScript). For example, "a retried delivery is never sent twice" or "a query run
as one tenant never returns another tenant's row". Keep the failing example the tool finds as a
plain test too.

## Tests that never flake

A test that sometimes fails teaches everyone to ignore the suite. Every test gives the same result
every run, on every machine, in any order:

- **No sleeping.** Wait for a condition (an element, a row, a message), with a timeout.
- **Inject what changes:** the clock, random numbers, generated ids and anything read from the
  environment are passed in, so a test sets them.
- **Each test owns its data:** it creates what it needs and leaves nothing a later test could see;
  no test depends on another having run first.
- **No real network** in inner tests: a fake at the boundary (§ Collaborators).

A flaky test is fixed the same day, or quarantined with a tag and an issue number until it is.
It is never retried until it happens to pass.

## Collaborators

Read [collaborators](references/collaborators.md) before substituting a dependency. Mock system boundaries, not code owned by the application.

## Outside systems: a fake and a contract test

For each outside system the code calls (a payment provider, an email service, another team's
API), the tests use a **fake**: a small in-process stand-in with the same interface, which
records what it was sent and answers as the real one would. A **contract test** runs the same
checks against the fake and against the real system, on a schedule (not on every PR), with test
credentials. When the outside system changes, the contract test fails before production does,
and the fake is updated to match.

## Python and server-rendered pages

The examples in the two references above are TypeScript. In a Python project, also read [Python and server-rendered pages](references/python.md): the same shapes in pytest, how to test a page the server renders, and where the boundaries are in a web app.
