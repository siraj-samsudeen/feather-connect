## 1. First-time setup — `acceptance-tests/` already exists; this change only adds to it

- [ ] 1.1 Merge `origin/main` into the branch (PR #15: `fcon db upgrade`, the two roles, ADRs 0009 to 0014); `uv lock` and `uv lock --project acceptance-tests` rather than merging the lock files by hand
- [x] 1.2 The suite's Docker support, delivered by the red/green of the first step that needs it: build the image once per run, containers and networks named after the run's port and a random part, a Postgres 18 container standing in for the administrator's, everything removed at the end, and a clear failure (never a skip) when Docker is not running (design, decision 3)

## 2. Step definitions — one task per pending step; each = fails for the right reason → implement → passes → commit

### Deployment: runs from its image

- [x] 2.1 deployment: Given a new, empty Postgres 18 database — red → green → commit
- [x] 2.2 deployment: When the operator upgrades the database with the product's image — red → green → commit
- [x] 2.3 deployment: And starts the product's image, giving it only the database's address — red → green → commit
- [x] 2.4 deployment: Then the product answers that it is ready to take work (the logs-and-health step, now against the product the scenario started) — red → green → commit
- [x] 2.5 deployment: And it shows the sign-in page — red → green → commit

### Deployment: follows the host's port

- [x] 2.6 deployment: And a host that gives the product the port 9090 — red → green → commit
- [x] 2.7 deployment: Then the product answers on port 9090 that it is running — red → green → commit
- [x] 2.8 deployment: And the container runtime reports the product as healthy — red → green → commit

### Deployment: upgrades its database by itself

- [x] 2.9 deployment: Given the standard setup on one machine, with a new, empty database — red → green → commit
- [x] 2.10 deployment: When the operator starts it — red → green → commit
- [x] 2.11 deployment: Then the product answers that it is ready to take work, with no upgrade run by hand — red → green → commit
- [x] 2.12 deployment: And the upgrade had finished before the product started — red → green → commit

### Deployment: reached only through its proxy

- [x] 2.13 deployment: Given the standard setup on one machine, with its site's name but no certificate — red → green → commit
- [x] 2.14 deployment: Then the sign-in page is served over an encrypted connection — red → green → commit
- [x] 2.15 deployment: And no other part of the setup can be reached from outside the machine — red → green → commit
- [x] 2.16 deployment: Given the standard setup is running on one machine — red → green → commit
- [x] 2.17 deployment: When the operator opens the site's plain, unencrypted address — red → green → commit
- [x] 2.18 deployment: Then the operator is sent on to the site's encrypted address — red → green → commit

## 3. What no scenario drives — each still arrives with the test or check that needs it

- [ ] 3.1 What the image holds: not root; no uv, no compiler, no `.env`, no `.git`, none of our tests — checked by `scripts/smoke-image.sh`
- [ ] 3.2 CI: the image job for amd64 on every PR (buildx, GitHub's build cache, the smoke test against the job's Postgres 18 with `fcon db upgrade`, then `/healthz`, `/readyz` and `/sign-in`); the same natively on an arm64 machine, on `main` only; actions pinned by commit, read-only token
- [ ] 3.3 CI's acceptance job runs the deployment scenarios (Docker on the runner)
- [ ] 3.4 Dependabot: the `docker` ecosystem for the `Dockerfile` (digests; never off Python 3.14), `/deploy` in the `docker-compose` entry
- [ ] 3.5 `deploy/.env.example`, and `docs/deploy.md`: the administrator's one-time SQL, one machine, a cloud host that runs containers, the settings; no host named
- [ ] 3.6 `AGENTS.md` § Project: the stack's line for the image and the setup (ADR 0015); `acceptance-tests/README.md`: the deployment scenarios need Docker

## 4. Completion

- [ ] 4.1 Run the full suite: every scenario passes, zero pending/undefined steps, HTML report generated
- [ ] 4.2 The end-of-change checks (ruff, pyright, vulture, deptry, pytest at 100%), and CI green on the PR
- [ ] 4.3 Run `openspec validate container-image --type change` before archive
