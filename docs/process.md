# How Feather Connect is built

Every piece of work goes from a GitHub issue to a merged pull request through the same steps. AI
agents do most of the writing, testing and reviewing, and the product owner decides at five fixed
points. This page explains each step, who does it, and how it maps to the roles and stages of a
usual software team. To set up a machine and take up an issue, see
[`CONTRIBUTING.md`](../CONTRIBUTING.md); the rules themselves are in [`AGENTS.md`](../AGENTS.md)
and the skills under [`.agents/skills/`](../.agents/skills/).

## The steps, start to finish

Steps marked **Owner** wait for the product owner's yes.

| # | Step | What happens | Who does it here | Usual role | Gate |
|---|---|---|---|---|---|
| 1 | Product definition | The requirements catalogue ([`docs/requirements.md`](requirements.md)) lists what the product must do, numbered (R7.21 and so on), with open decisions (D-01…) and a milestone for each: M1 first, M2 later. | Owner with the manager session | Product owner, business analyst | **Owner:** scope and milestones |
| 2 | Backlog | The work becomes a GitHub issue with a rating (red, yellow, green or chore) and "blocked by" links. One worker takes one issue at a time. | Manager session | Project manager, scrum master | **Owner:** what comes next |
| 3 | Design, point by point | For each point: what it means, the alternatives with their merits and drawbacks, one recommendation, and mockups for any screen. The agreed design is written into the issue. | Manager proposes, owner decides | Business analyst, architect, UX designer | **Owner:** each point |
| 4 | Start the build | A build session starts in its own git worktree and branch from `main`, with a brief made from the issue and a mode: autopilot, build or learning. | Manager session, or a developer | Tech lead takes the work | **Owner:** the mode |
| 5 | Planning (OpenSpec) | **Proposal:** why and what. **Specs:** requirements with Gherkin scenarios that later run as acceptance tests. **Design and ADRs:** how, and the lasting decisions. **Tasks:** the ordered steps. An independent reviewer checks the specs. | Build session | BA (proposal), test lead (scenarios), architect (ADRs), tech lead (tasks) | **Owner:** approve the planning |
| 6 | Draft pull request | One PR per change, opened early, so the work is visible while it grows. | Build session | Tech lead | — |
| 7 | Build (outside-in TDD) | `senior-qa` writes the acceptance scenarios (behave with Playwright) and commits them failing. `senior-dev` makes them pass, writing unit tests first: red, green, refactor. The build session checks each batch and hands out the next. | `senior-qa`, `senior-dev`, build session | QA automation, developer, tech lead | — in autopilot |
| 8 | Continuous integration | Each push runs ruff, pyright (strict), vulture, pytest, the acceptance suite, spec validation and a container image build. Windows and macOS tests and mutation testing report without blocking until M1. A build pushes at a few agreed points, not after every commit. | GitHub Actions | DevOps, build engineer | — |
| 9 | Verification | **UI work:** an independent verifier uses the real pages at 1280 px against the numbered checklist in the issue. **Code review** by Codex or a different Claude model, for what testing can't show: security, permissions, data, server logic. Findings are sorted into three levels; at most three review rounds. | Verifier agent, reviewer agent | QA tester or UAT, peer reviewer, security reviewer | **Owner:** an adversarial review only if agreed |
| 10 | Demo | Short review videos of the working flow. | Build session | Sprint review | **Owner:** accept |
| 11 | Close the specs | `openspec verify` checks the code against the planning; archiving moves the change's specs into [`openspec/specs/`](../openspec/specs/), the living description of the product. | Build session | Technical writer, BA | — |
| 12 | Release gate | The manager checks the PR against the issue point by point; the owner merges with a merge commit and the issue closes. CI then builds the image on `main` for amd64 and arm64. | Manager checks, owner merges | Release manager, change board | **Owner:** merge |
| 13 | Learning | Preferences and lessons are kept for the next change. Process fixes go to the shared template, not this repo. | Every session | Retrospective | — |

## Roles

The usual roles all exist; most are filled by AI sessions, each with a narrow job. A *session* is
one agent conversation; a *subagent* is a helper that a session starts for one job and that reports
back to it. A developer can take any of these roles by hand: the steps and the checks are the same.

| Usual role | Who fills it here | What they own |
|---|---|---|
| Product owner, sponsor | The owner (a person) | Scope, priorities, every design decision, planning approval, the merge |
| Business analyst | Manager session, then the build session | The requirements catalogue, issue texts, the proposal and specs |
| Architect | Manager session | Alternatives and recommendations, recorded as ADRs in [`adr/`](../adr/) |
| UX designer | Manager session | Mockups in the design step; the verifier later checks the real pages against them |
| Project manager, scrum master | Manager session (stays on `main`) | Issues, ratings, dependencies, starting build sessions, reporting progress |
| Tech lead | Build session (one per issue) | Planning, task order, checking each batch, pushing, the PR |
| Test lead, QA automation | `senior-qa` subagent | Turning the Gherkin scenarios into runnable acceptance tests |
| Developer | `senior-dev` subagent | Production code, written test first |
| QA tester, UAT | Independent verifier, then the owner's video review | Checking the real product from the outside |
| Peer and security reviewer | Codex, or a different Claude model than the author | Security, permissions, data, server logic |
| DevOps, release engineer | CI workflows, the container image, [`docs/deploy.md`](deploy.md) | Builds, checks, deployable images |

## Where people decide

Agents work alone between these points; nothing passes one without a person saying yes.

1. **Agree the design**: each point of the issue, before any code.
2. **Choose the mode**: how often the build stops to ask.
3. **Approve the planning**: proposal, specs, design and tasks.
4. **Accept the demo**: the verifier's results and the review videos.
5. **Merge**: only the owner merges a change into `main`.

| Mode | The build stops for you… | Use it when |
|---|---|---|
| Autopilot | at the planning approval and at the end | The design is settled and you want speed |
| Build | at each step: every planning artifact, each batch of tests and code | You want to steer as it goes |
| Learning | at each step, and explains what it did and why | You are new to the code or the method |

Review findings are sorted before anyone sees them (`AGENTS.md` § Review guidelines):

| Level | Meaning | What happens |
|---|---|---|
| 1 | Breaks core functionality: wrong results, data loss, a security hole | Fixed now |
| 2 | Plausible in real use, limited impact | Fixed if cheap, otherwise one issue for all of them |
| 3 | Rare or theoretical | One line in the PR under "Deliberately not handled" |

## Which SDLC this is

- **Overall: agile, closest to Kanban.** Work is pulled one issue at a time per worker; there are
  no fixed sprints. Milestones M1 and M2 act as release goals.
- **Each issue is a small V-model.** Every step on the left is proved by a check on the right:

  | Defined by | Proved by |
  |---|---|
  | Requirements and Gherkin scenarios | Acceptance tests (behave, Playwright) |
  | Design and ADRs | Code review, independent verifier |
  | Code-level behaviour | Unit tests (pytest), types, mutation testing |

- **Spec-driven, with BDD and TDD.** The spec is the source of truth. Its scenarios run as tests,
  and tests are written before code. When a change is archived its specs join `openspec/specs/`,
  so the specs always describe the product as it is.
- **Small changes, one PR each.** One issue, one worktree, one branch, one PR, from proposal to
  archive. Each change stays reviewable, and two builds can run side by side without touching each
  other.

## A worked example: sign-in (issue #16)

The first feature behind the dashboard. Every dashboard page needs a signed-in user, so the issue
is rated red.

1. **Issue filed**, blocked by the storage issue (#12), which gives it tables, transactions and the
   audit log.
2. **Design agreed in 12 points** (owner). For example: argon2id for passwords (measured at 34 ms
   and 19 MB per hash, against scrypt's 2.2 s and 128 MB); sessions kept in the database, so
   signing out ends them everywhere; at most 3 failed sign-ins per 15 minutes before the waits
   grow, with no lockout; the last administrator can't be removed.
3. **Build started in autopilot** (owner) in its own worktree, with the 12 points and descriptions
   of the four pages as its brief.
4. **Planning approved** (owner): a proposal and three spec changes (users and access, dashboard
   basics, deployment), checked by an independent reviewer first.
5. **Build:** `senior-qa` commits the failing scenarios in batches and `senior-dev` makes them
   pass. Pushes happen at three agreed points, so CI runs three times.
6. **Then:** the verifier at 1280 px, the code review (security, sessions, audit), the videos, the
   archive, and the owner's merge.

## Glossary

| Term | Meaning |
|---|---|
| Issue rating | Red: blocks other work. Yellow: needed soon. Green: can wait. Chore: upkeep with no feature. |
| Worktree | A second working folder of the same git repository, on its own branch, so two pieces of work never touch the same files. |
| OpenSpec | The tool and folder layout for planning a change: proposal, specs, design, tasks; then verify and archive. |
| Change | One unit of work in OpenSpec, matching one issue and one PR. |
| Delta spec | The part of a spec that a change adds or modifies; merged into the living specs at archive. |
| Gherkin | Given / When / Then scenarios in plain words, which also run as tests. |
| ADR | Architecture decision record: one decision, its alternatives and its consequences. |
| Outside-in TDD | Start from a failing acceptance test of what the user sees, then write unit tests and code inward until it passes. |
| Red, green, refactor | Write a failing test, make it pass simply, then tidy the code with the tests still passing. |
| Manager session | The agent session that stays on `main`, designs with the owner, files issues and starts builds. |
| Build session | The agent session that carries one issue from planning to PR in its own worktree. |
| Subagent | A helper the build session starts for one job (`senior-qa`, `senior-dev`, the verifier) that reports back. |
| Independent verifier | An agent that never saw the code, checking the real pages against the issue's numbered checklist. |
| Adversarial review | An extra, deliberately critical review by a different model; only with the owner's consent. |
| Mutation testing | Changing the code slightly to check that the tests notice; run weekly with mutmut. |
| M1, M2 | Milestones. M1 is the first release; M2 follows. |

## Questions

**Do I have to use AI agents?** No. The steps, the files and the checks are the same for a person.

**How do decisions reach my machine?** Through git and GitHub: conventions in `AGENTS.md`,
decisions in `adr/` and the specs, designs in the issues. Nothing important lives only in a chat or
on one laptop, so changing machine or tool loses nothing.

**Why one PR per change, from proposal to archive?** The planning, the code and the final specs
are reviewed together, so a reader sees why, what and how in one place, and `main` never holds half
a change.

**Can two people build at the same time?** Yes, on different issues in different worktrees, each
with its own ports and database. See `CONTRIBUTING.md` § Working beside other people.

**What if review keeps finding things?** At most three review rounds. After the third, the build
stops and the owner decides the next step.

**Why are some checks relaxed until M1?** To move fast while the product takes shape: mutation
testing is a weekly report, the Windows and macOS tests don't block, and dependency updates are
monthly. They tighten before the M1 release (#5). Strict type checks and dead-code checks stay on.

**What isn't covered yet?** Running a live deployment (monitoring, incidents), formal releases with
signed images, and feedback from real users. These come as the product reaches its first users.
