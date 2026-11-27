---
name: change-modes
description: The three ways an OpenSpec change can be built (autopilot, build, learning), how the mode is chosen and switched in the session, the defaults that are never asked, and the git flow (a worktree, a branch and one PR per change, from proposal to archive). Use when creating, resuming or applying an OpenSpec change, when the human names a mode ("autopilot", "learning mode"), or when an openspec-* skill ends a step by asking whether to continue.
---

# Change modes

## The three modes, chosen in the session

Every change uses the one schema, upstream's `intent-driven`, unchanged
(`openspec new change <name>`). Its planning artifacts are the same in every mode: specs carry
fenced Gherkin that the acceptance runner executes, and `tasks.md` is `spec-as-source`'s
acceptance-test-first list. The mode decides only who builds and where the human stops:

| Mode | Who it is for | How apply runs |
|---|---|---|
| **Autopilot** | Work the human wants done, not followed step by step | `senior-qa` writes the acceptance tests, `senior-dev` the code, down the same task list; no per-test stops |
| **Build** (default) | A maintainer who wants control with few stops | `outside-in-tdd`: one stop per test for the human's prediction; red, green and refactor as separate commits, in the main session |
| **Learning** | A student or newcomer who learns from every command | Build, plus a stop before every command: show it, explain it, wait for "run", interpret the result (`outside-in-tdd` § Learning mode) |

**The mode is session state, never written into the change.** No `**Mode:**` line, no
per-mode schema or task list: the human switches mode whenever they like ("go autopilot from
here"), and a switch changes no file. A session that resumes a change without being told the
mode uses build and says so, so the human can switch.

In every mode the planning artifacts are reviewed by whoever decides them (§ Who decides;
grill-me still applies).

## Who decides

The owner makes the product decisions; developers build, each with their own agent. A
developer's agent sees only the repo and GitHub, so every decision it needs is in the issue,
the specs, an ADR or `AGENTS.md`.

| Decision | Who | Recorded in |
|---|---|---|
| Scope, what comes next, milestones | Owner | The issue and its rating |
| The design: behaviour, screens, security choices | Owner, point by point | The issue's agreed design |
| The proposal and specs: what the change does | Owner | The change's first commits |
| A lasting technical choice: a new dependency, pattern or data layout | Developer proposes, owner decides | An ADR |
| The technical design inside the agreed design | The developer running the build | `design.md`, `tasks.md` |
| Code, tests, refactoring | The developer and their agent | Commits |
| The merge | Owner | A merge commit |

When the owner runs the build, the owner approves `design.md` and `tasks.md` too.

**A product question goes to the owner on the issue.** When the agreed design does not say what
should happen in a case the build finds, the agent stops that task and asks the owner in a
comment on the issue; it never decides it in code. The answer is added to the issue's agreed
design, so the next agent sees it. Technical questions are the developer's.

Changes created before this version of the template (schema `intent-driven-with-human-control`,
or a `**Mode:**` line in the proposal) keep their files; finish them in whatever mode the session
uses.

## Defaults — never ask

Formatting and tooling choices are not questions for the human:

- Diagrams: Mermaid, lightweight C4-inspired.
- ADRs: MADR minimal (`.agents/skills/architectural-decision-records/preferences.md`), in the
  folder `adr_dir` names in `.copier-answers.yml` (`adr/` unless the project says otherwise),
  numbered after the highest existing one. An accepted ADR is never edited; a new ADR supersedes
  it.
- Acceptance-test stack: `stack:` in `openspec/config.yaml` (`acceptance_stack` in the answers).
- Code style: the `maintainable-code` skill (simplicity, names, a description on every file
  and function, structure, errors, types), with its checks in the linter's configuration.
- Simplicity limits: a complexity limit per function (ruff `C90`, eslint `complexity`, both at
  10), a length limit per function and per file set from the project's own code, and a soft
  limit of about 600 changed lines of code per PR, tests, specs and migrations aside. An
  exception is marked in the code with its reason.
- Supply chain: CI audits the locked dependencies (`pip-audit`, `npm audit`), and GitHub's
  dependency review and secret scanning are on. A new dependency comes with an ADR saying why,
  and that the package is real and maintained: agents sometimes suggest packages that do not
  exist, and attackers register those names.
- Traceability: when the project keeps a requirements catalogue, a spec names the catalogue
  IDs it covers, and `scripts/trace_requirements.py` lists the IDs no spec names.

## Definition of Done

A change is done when every line holds. The PR template repeats this list as checkboxes.

- [ ] Every scenario of the change passes, with no pending or undefined step.
- [ ] Every end-of-change check is clean (`outside-in-tdd` § Reconcile): coverage, unused code,
      types, complexity, descriptions, the dependency audit.
- [ ] Every new or changed file, class and function has a true description (`maintainable-code`).
- [ ] A change that touches sign-in, permissions, data or input has its threat check, and the
      checklist holds (`security-baseline`).
- [ ] The review is done and its findings triaged, in at most three rounds; for UI, the
      independent verifier's checklist passes.
- [ ] What the change logs, measures and alerts on is in place, with its runbook entry
      (`openspec/config.yaml`, proposal rules).
- [ ] Docs that the change makes untrue are updated: the README, `docs/architecture.md`,
      `docs/runbook.md`, the deployment guide.
- [ ] The owner has watched the review videos.
- [ ] The change is archived as the branch's last commit, and the PR body lists what was
      deliberately not handled.

## Releases

- **Versions by meaning** (semver): the major number goes up when a user or an integration must
  change something (a removed option, an incompatible API, a data change they must act on); the
  minor for a new feature; the patch for a fix. Label such a PR `breaking`.
- **Release notes** are drafted from the merged PRs' titles and labels
  (`.github/release-drafter.yml`, `.github/workflows/release.yml`); a PR title is written for
  the person who reads the notes.
- **The release checklist**, before the owner publishes: every change in it meets the
  Definition of Done; CI is green on `main`; the upgrade is tried on a copy of the last release's
  data; the notes say what a user must do, if anything; the runbook covers every new alert.
- **Every risky change can be undone.** Its `design.md` says how: a feature flag that turns it
  off, or a data change that only adds (new tables, optional columns), so the previous version
  still runs on the new data. Removing or renaming waits for a later release.

## Continuing — overrides the openspec-* skills

When an `openspec-*` skill ends a step by asking whether to continue ("STOP and wait for user
direction", "Ready to create the first artifact?", "Want to continue?"), the `outside-in-tdd`
stop rule wins: continue to the next artifact without asking. Those skills are generated by the
OpenSpec CLI, so this override lives here rather than in them.

## Git — one worktree, one branch, one PR per change

The manager session stays on `main` in the main checkout. Each issue gets a task session in its
own worktree (the `issue-workflow` skill), and the change lives on that worktree's branch from
proposal to archive:

0. **Worktree**: `git worktree add ../<repo>-issue-<n> -b issue-<n>-<change-name> main`, with
   its own ports and its own database, so it can run beside the main checkout and other
   worktrees.
1. **Planning**: the planning artifacts (proposal, specs, design, adr, tasks), one commit each.
   When the last is approved, push the branch and open the PR; it stays open.
2. **Build**: the code, tests and `tasks.md` ticks, on the same branch. **Push at agreed
   points**, two or three per change, named in the build brief: for example when the
   foundation passes, after the riskiest batch, and before the verifier and the review. Not
   after every commit: CI runs a few times per change, and each run tells something. In
   autopilot the subagents commit and never push; the session pushes.
3. **Review videos**: the acceptance suite's review videos are recorded (the
   `acceptance-test-authoring` skill) and the owner watches them.
4. **Archive**: after the owner has watched the videos, sync the specs and archive the change,
   as the branch's last commit.
5. **Merge**: the owner merges with a merge commit. Then the worktree is removed.

This replaces the upstream `openspec-git-discipline` flow (a proposal PR merged first, then an
implementation PR, then archive on `main`). Other differences from that skill, which asks
before every commit, branch and PR:

- Approving a step is the human asking for its commit; do not ask again.
- When the last planning artifact (or the reconcile) is approved, push the branch and open its
  PR without asking. Merging is the owner's.
- Merge with merge commits, never squash, so the red/green/refactor steps survive.
