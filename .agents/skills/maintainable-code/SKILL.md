---
name: maintainable-code
description: "Use when writing, refactoring or reviewing code: keep it as simple as the tests allow, readable by a person new to it, and maintainable for years. Every file and every function says what it is for. Covers simplicity, naming, descriptions (docstrings and comments), structure, errors, types, and the checks that enforce them."
---

# Maintainable code

The code is written by agents but kept by people. A developer new to a file should be able to
tell, in a minute, what it is for, how to use it and why it is built that way, without asking
anyone and without reading the rest of the codebase. Every rule below serves that.

When a rule here and a project convention (`AGENTS.md` § Project) differ, the project wins.

## 1. Simple first

- **Write the simplest code that makes the tests pass.** No layer, class, option, hook or
  configuration that no test and no requirement asks for. A second use is the time to generalise,
  not the first.
- **Plain functions and plain data first.** A class when there is state to keep together with the
  rules that guard it; a protocol or interface when there are really two implementations.
- **The standard library before a dependency**, and a dependency only with an ADR.
- **One way to do a thing.** When the codebase already has a pattern (how it reads settings,
  talks to the database, reports a problem), use it; don't add a second.
- **Delete rather than keep:** dead code, commented-out code, unused parameters, flags nobody
  sets. Git remembers them.
- **Clear beats clever.** No one-liner that needs a second read, no trick a newcomer must look up.
  Spell it out over a few lines.

## 2. Names

- Names say **what a thing is or does in the domain's words**: the words of the specs and the
  glossary (`delivery`, `slice`, `retry_after`), not `data`, `info`, `handle`, `manager`, `util`.
- A function is named for what it gives back or what it does (`overdue_deliveries`,
  `send_reminder`); a boolean reads as a question (`is_active`, `has_expired`).
- Units are in the name when the type doesn't carry them: `timeout_s`, `size_bytes`.
- No abbreviations a newcomer would have to guess. Short names only in tiny scopes (`i` in a
  three-line loop).
- A number or string with a meaning becomes a named constant, with a line saying where it comes
  from (`MAX_ATTEMPTS = 5  # the owner's limit, issue 16`).

## 3. Descriptions: every file and every function

Descriptions are part of the code, written with it and changed with it. A description that is no
longer true is a bug.

**Every file starts with a description** (a module docstring in Python, a header comment in
JavaScript and TypeScript) of two to six lines:

- what the file holds and the one job it does;
- where it fits: who calls it, what it calls, and what it must never do (for example "never
  imports the web layer");
- the spec, requirement, ADR or issue that explains why, when there is one.

**Every function, method and class has a description**, public or private:

- the first line says what it does or gives back, in domain words, as a sentence;
- then, only when the names and types don't already say it: what the inputs mean, what comes
  back, what it raises or refuses and when, and any side effect (writes to the database, sends a
  message, reads the clock);
- why, when the obvious approach was not taken.

Don't restate the code ("increments i"). Don't describe how it used to work. Keep it short: a
one-line description is right for most functions.

An `__init__` that only takes and keeps its arguments, and a standard method such as `__repr__`,
need no description of their own: the class's description covers them.

A test's name says the behaviour it proves, so a test function needs no description of its own;
a test file's description names what it tests and, where there is one, the spec it follows.

**Comments inside a function say why, never what.** They explain a choice, a constraint, a
workaround (with its link), or an order that matters. When code needs a comment to explain what
it does, rename or split it first.

No `TODO` without an issue number (`# TODO(#42): ...`).

## 4. Structure

- **One job per function.** If its description needs an "and", split it. Aim for under about 40
  lines; the project's limit is in `change-modes` § Defaults.
- **Shallow:** return early for the special cases, so the main path reads straight down; no more
  than three levels of nesting.
- **One concept per file**, named after it; aim for under about 400 lines.
- **Logic apart from input and output.** The rules (what to deliver, whether a password is good
  enough) are plain functions that take values and return values; reading the database, the
  clock, the network or the environment happens at the edges and hands them values. The rules can
  then be tested without any of those.
- **Dependencies point one way:** the domain doesn't import the web framework, the database
  driver or the command line; those import the domain.
- **No global mutable state.** Settings are read in one place and passed in.
- **Few parameters:** more than four is a sign two things are mixed, or a small value object is
  missing. Use keyword arguments for anything a reader could confuse.

## 5. Errors

- **Fail loudly and early, and say what to do.** An error message names what was wrong, the value
  that was wrong (never a secret), and what the person can do about it.
- **Never swallow an error:** no bare `except:`/`catch {}` and no `pass` without a comment saying
  why it is safe.
- **Check input at the edges** (a request, a file, a command's arguments); inside, trust the types.
- Expected problems are values or specific exceptions the caller handles; a stack trace is only
  for a real bug.

## 6. Types

- Full type hints in Python (pyright strict), strict TypeScript. No `Any` or `any` except at a
  boundary with untyped data, where it is converted at once.
- A type for each domain idea that has rules (`UserName`, `Money`, an enum for a fixed set),
  rather than a bare `str` or `int` passed around.
- Immutable by default: frozen dataclasses, `readonly`, tuples.

## 7. Changing code

- **Tidy first, in its own commit:** a rename or a move is a `refactor:` commit that changes no
  behaviour, before the commit that changes behaviour.
- **Leave each file a little clearer than you found it**: fix a misleading name or a stale
  description you meet, in the same refactor commit.
- **Follow the formatter;** layout is never argued about.

## Checks that enforce it

These run with the end-of-change checks (`outside-in-tdd` § Reconcile) and in CI:

| Rule | Python (ruff) | JavaScript / TypeScript (eslint) |
|---|---|---|
| Every file, class and function has a description | `D` (pydocstyle) with `convention = "google"`, so a first line may say what comes back; `D1` reports a public file, class or function without one; `D105` and `D107` off (the class covers them); tests exempt from `D103` | `jsdoc/require-jsdoc` (eslint-plugin-jsdoc) for functions and classes |
| Complexity per function | `C90`, `max-complexity = 10` | `complexity: 10` |
| Branches, statements, parameters | `PLR0912`, `PLR0915`, `PLR0913` (`max-args = 4`) | `max-depth: 3`, `max-lines-per-function: 40`, `max-params: 4`, `max-lines: 400` |
| No swallowed errors | `BLE`, `S110`, `E722` | `no-empty` |
| No commented-out code | `ERA` | `no-warning-comments` for TODOs without an issue |
| Types | pyright strict | `strict` in `tsconfig.json`, `@typescript-eslint/no-explicit-any` |

The tools see only public names: a private function's description, a file header in JavaScript, and whether a description is still true are for the review. What no tool checks, the review does: **would a developer new to this file understand what it
is for and why, in a minute?** A review that answers no is a level 2 finding (`AGENTS.md`
§ Review guidelines).

## Example (Python)

```python
"""Reminders for deliveries that have waited too long (spec: deliveries, R7.4).

Decides which deliveries are overdue; the worker sends the reminders. Never reads the
clock or the database itself: the caller passes the time and the deliveries in.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

OVERDUE_AFTER = timedelta(hours=4)  # the owner's threshold, issue 31


@dataclass(frozen=True)
class Delivery:
    """A delivery as the reminder rules see it: who it is for and when it was queued."""

    destination: str
    queued_at: datetime


def overdue_deliveries(deliveries: list[Delivery], now: datetime) -> list[Delivery]:
    """The deliveries queued more than `OVERDUE_AFTER` before `now`, oldest first."""
    overdue = [d for d in deliveries if now - d.queued_at > OVERDUE_AFTER]
    return sorted(overdue, key=lambda d: d.queued_at)
```
