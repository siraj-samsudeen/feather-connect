# AGENTS.md

- For OpenSpec propose/apply/verify/archive workflows, use the `change-modes` skill: one worktree,
  branch and PR per change, from proposal to archive. It overrides the two-PR flow of the
  upstream `openspec-git-discipline` skill.
- Work starts from a GitHub issue and goes one issue at a time per worker; the manager session
  stays on `main`. See the `issue-workflow` skill (issue body, red/yellow/green rating, blocked by,
  task sessions and worktrees, the UI route).

## Review guidelines

These apply to every review of a change: local reviews before a PR, and PR reviews (Codex's
GitHub reviewer reads this section).

**Stance.** The product evolves fast. Getting the functionality to fit the need matters more than
perfect code. Do not add code, or follow-up issues, for things unlikely to happen.

**Who reviews locally.** Codex, if it is available (`codex review --base main`); otherwise a
review by a different Claude model than the one that wrote the code.

**UI changes take the UI route** (the `issue-workflow` skill): mockups, a numbered checklist in
the issue, then an independent verifier against the real UI, before the owner sees code. A code
review covers only what a person can't see when testing: security, permissions, data, server
logic. No review for docs, cosmetic changes or very minor fixes.

**Adversarial review only with the human's consent.** When the agent judges the work complex or
critical — security, permissions, data — it proposes an adversarial review (or the
`adversarial-authoring` skill for a planning artifact) in one line, with the reason, and runs it
only if the human says yes. It is never mandatory.

**At most 3 review rounds.** After the third, stop and propose the next step to the human instead
of starting a fourth.

**Triage every finding before presenting it:**

1. **Breaks core functionality** — wrong results, data loss, a security hole → fix now.
2. **Plausible in real use, limited impact** → fix it if cheap; otherwise file **one** issue for
   all such findings, not one per finding.
3. **Rare or theoretical edge case** → one line in the PR body under "Deliberately not handled".
   No code, no issue.

Present the findings grouped by these three levels. In a PR review, report level 3 findings as
level 3, not as requests for changes.
