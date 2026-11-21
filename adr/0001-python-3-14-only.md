# 0001. Python 3.14 only

- Status: accepted
- Date: 2026-11-21
- Decision-makers: the project owner
- Decided in: issue #4, point 1 (catalogue decision D-12)

## Context and Problem Statement

The catalogue's D-12 asks for the lowest supported language version, to be settled by the first
change. Flows are Python code written against the flow library, and the server is Python too. Each
version supported is one more to test on every operating system. The deployed server runs in a
container on a cloud host, built by the project, and development runs through uv, which installs
the Python a project asks for.

## Considered Options

- Python 3.14 only, for development and for the deployed server.
- A range of versions (for example 3.12 and later), so flow authors can use the Python they have.
- Python 3.15, the newest release.

## Decision Outcome

Chosen option: "Python 3.14 only", because the server ships in the project's own container and uv
gives every developer the right Python, so a range buys nothing but test work. Python 3.15 was
ruled out on 13-Nov-2026: PyYAML had no Windows build for it, so installing it there needed a C++
compiler. Every package declares `requires-python = ">=3.14"`.

### Consequences

- Good, because one version is tested, on Windows, macOS and Linux.
- Good, because the newest typing and standard library are available everywhere.
- Bad, because a flow author must use 3.14; uv installs it, but a team on an older Python has to
  move.
- Moving to a newer version is a later change with a new ADR that supersedes this one.
