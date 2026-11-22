## 1. First-time setup — `acceptance-tests/` already exists; this change only adds to it

- [x] 1.1 The suite's stack gives the server it starts a random `FCON_SECRET_KEY`, and the image's containers one too, so the scenarios already on `main` keep passing once the key is required; `scripts/worktree_env.py` writes a random key into `.env` (design, Migration Plan)
- [ ] 1.2 The suite's support for users, delivered by the red/green of the first step that needs it: a page object for the command line's `fcon users` (password on stdin), one for the overview, one for choose-password, one for the expired form, and a way to read the scenario database's audit log, sessions and attempts; every URL, command and text in page objects, none in steps

## 2. Step definitions — one task per pending step; each = fails for the right reason → implement → passes → commit

### Users and access: a refused sign-in gives no hint

- [x] 2.1 users-and-access: Given "ann" is an administrator with the password "blue-harbour-lamp" — red → green → commit
- [x] 2.2 users-and-access: the existing refusal steps, now against a real user, and "A name nobody has is refused in the same words" — red → green → commit

### Users and access: the first administrator

- [x] 2.3 users-and-access: Given a new install with no users — red → green → commit
- [x] 2.4 users-and-access: When the operator adds the user "ann" from the command line, with the password "blue-harbour-lamp" — red → green → commit
- [x] 2.5 users-and-access: Then the user sees the overview — red → green → commit
- [x] 2.6 users-and-access: And the user is shown as "ann", an administrator — red → green → commit
- [ ] 2.7 users-and-access: And the product's settings name "ann" as the first administrator — red → green → commit
- [ ] 2.8 users-and-access: When the operator starts the product — red → green → commit
- [ ] 2.9 users-and-access: Then its log gives a one-time password for "ann", and says to sign in and choose a new one — red → green → commit
- [ ] 2.10 users-and-access: And after a restart its log gives no password again — red → green → commit

### Users and access: sign in, and back to the page asked for

- [ ] 2.11 users-and-access: And the user is still signed in when they open the dashboard again — red → green → commit
- [ ] 2.12 users-and-access: When the user opens the address of run 42 / And signs in as … — red → green → commit
- [ ] 2.13 users-and-access: Then the user is at the address of run 42 — red → green → commit
- [ ] 2.14 users-and-access: When the user follows a sign-in link that would send them on to another site — red → green → commit

### Users and access: a given password works once; passwords hard to guess

- [ ] 2.15 users-and-access: Given "ben@example.com" was added as an operator with the first password "given-once-0001" — red → green → commit
- [ ] 2.16 users-and-access: Then the user is asked to choose their own password before going on — red → green → commit
- [ ] 2.17 users-and-access: And the user sees the overview once they have chosen "ben-own-password-1" — red → green → commit
- [ ] 2.18 users-and-access: And the user has signed in as "ben@example.com" with the password "given-once-0001" — red → green → commit
- [ ] 2.19 users-and-access: When the user opens the dashboard without choosing a password — red → green → commit
- [ ] 2.20 users-and-access: And the user has signed in as "ben@example.com" and chosen the password "ben-own-password-1" — red → green → commit
- [ ] 2.21 users-and-access: When the user signs out, and signs in as "ben@example.com" with the password "given-once-0001" — red → green → commit
- [ ] 2.22 users-and-access: When the user chooses the password "<password>" — red → green → commit
- [ ] 2.23 users-and-access: Then the password is refused, because it is <reason> (too short, too common, the user's own name) — red → green → commit
- [ ] 2.24 users-and-access: And the user is still asked to choose their own password — red → green → commit

### Users and access: sessions end, and run out

- [ ] 2.25 users-and-access: And the user is signed in as "ann" on two computers — red → green → commit
- [ ] 2.26 users-and-access: When the user signs out on one of them — red → green → commit
- [ ] 2.27 users-and-access: Then the user is no longer signed in on the other — red → green → commit
- [ ] 2.28 users-and-access: And the user has signed in as "ben@example.com" with the password "given-once-0001" on two computers / When the user chooses the password "ben-own-password-1" on one of them — red → green → commit
- [ ] 2.29 users-and-access: Given "ben@example.com" is an operator with the password "ben-own-password-1" / And the user is signed in as "ben@example.com" — red → green → commit
- [ ] 2.30 users-and-access: When the operator disables "ben@example.com" from the command line — red → green → commit
- [ ] 2.31 users-and-access: Then the user is no longer signed in / And signing in as … is refused — red → green → commit
- [ ] 2.32 users-and-access: When the user comes back after 13 hours without using the dashboard / Then the user is asked to sign in again — red → green → commit

### Users and access: guessing is slowed

- [ ] 2.33 users-and-access: And someone has failed to sign in as "ann" 3 times in a row — red → green → commit
- [ ] 2.34 users-and-access: When the user signs in as "ann" with the password "blue-harbour-lamp" at once — red → green → commit
- [ ] 2.35 users-and-access: Then the sign-in is refused, in the same words as a wrong password — red → green → commit
- [ ] 2.36 users-and-access: And signing in as "ann" with the password "blue-harbour-lamp" works once the wait has passed — red → green → commit
- [ ] 2.37 users-and-access: And someone at the user's address has failed to sign in as 3 different names — red → green → commit

### Users and access: forged forms are refused

- [ ] 2.38 users-and-access: Given the user is signed in as "ann", with the overview open / And the user has since signed out and back in from another tab — red → green → commit
- [ ] 2.39 users-and-access: When the user signs out from the overview opened before — red → green → commit
- [ ] 2.40 users-and-access: Then the user is told the form has expired, and to reload the page / And the user can go on to the overview from there / And the user is still signed in — red → green → commit
- [ ] 2.41 users-and-access: When a page on another site sends the dashboard a sign-out form / Then the form is refused as expired — red → green → commit

### Users and access: the command line, and always an administrator

- [ ] 2.42 users-and-access: When the operator makes "ben@example.com" a viewer from the command line / And the user opens the dashboard again / Then the user is shown as "ben@example.com", a viewer — red → green → commit
- [ ] 2.43 users-and-access: And the operator has disabled … / When the operator enables "ben@example.com" from the command line — red → green → commit
- [ ] 2.44 users-and-access: Given "ann" is the only administrator / When the operator makes "ann" an operator from the command line — red → green → commit
- [ ] 2.45 users-and-access: Then the change is refused, because "ann" is the only administrator / And "ann" is still an administrator — red → green → commit
- [ ] 2.46 users-and-access: When the operator disables "ann" from the command line (refused) — red → green → commit

### Users and access: every sign-in is recorded

- [ ] 2.47 users-and-access: Then the audit log records a refused and a successful sign-in for "ann", from the user's address — red → green → commit
- [ ] 2.48 users-and-access: And no password appears anywhere in the audit log — red → green → commit

### Dashboard basics

- [ ] 2.49 dashboard-basics: Given the product's environment is named "staging" / And the user is signed in as "ann", an administrator — red → green → commit
- [ ] 2.50 dashboard-basics: Then the page names the environment "staging" — red → green → commit
- [ ] 2.51 dashboard-basics: And the user opens the overview, the page to choose a password and an expired form (accessibility, light and dark) — red → green → commit

### Deployment

- [ ] 2.52 deployment: And starts the product's image, giving it only the database's address, and the secret key every install needs — red → green → commit
- [ ] 2.53 deployment: And starts the product's image, giving it only the database's address / Then the product does not start / And it says the secret key is missing, and how to make one — red → green → commit
- [ ] 2.54 deployment: And the user has the sign-in page open / When the operator restarts the product with a new secret key, naming the old one as previous — red → green → commit
- [ ] 2.55 deployment: When the user signs in as "ann" through the site's encrypted address / Then the audit log records the sign-in from the user's own address, not the proxy's — red → green → commit
- [ ] 2.56 deployment: And the product's image runs with no proxy trusted / When a visitor opens two pages through a proxy that names the visitor's address / Then its log warns once, not twice … — red → green → commit

## 3. What no scenario drives — each still arrives with the test or check that needs it

- [ ] 3.1 The 7-day limit on a session, a secret key too short, two password entries that differ, a user name that breaks the rules, a password over 128 characters: inner tests
- [ ] 3.2 Equal time for every refusal: a made-up name still runs one argon2id check against a dummy hash (inner test on the call)
- [ ] 3.3 A hash redone at sign-in when the strength rises; `fcon users list`; the rights table and `require(ctx, action)` with a refusal audited: inner tests
- [ ] 3.4 Every table checked against `tables.py`, secret columns never in the audit (hashes, tokens, session ids), every index starting with `tenant_id`: inner tests beside the store's
- [ ] 3.5 `.env.example`, `deploy/.env.example`, `deploy/compose.yaml` (the secret key, the trusted proxy), `docs/deploy.md` (the five settings, making the first administrator both ways), `scripts/smoke-image.sh` and CI's image job pass a secret key
- [ ] 3.6 `AGENTS.md` § Project and `CONTRIBUTING.md`: the secret key in a worktree's `.env`, making a first user for development
- [ ] 3.7 The common-password list in the package, with where it came from and its licence

## 4. Completion

- [ ] 4.1 Run the full suite: every scenario passes, zero pending/undefined steps, HTML report generated
- [ ] 4.2 The end-of-change checks (ruff, pyright, vulture, deptry from each package, pytest at 100%), and CI green on the PR
- [ ] 4.3 The UI route: an independent verifier at 1280 px against issue 16's checklist; then the code review (security, sessions, the audit), at most 3 rounds
- [ ] 4.4 Review videos of the sign-in journey, watched by the owner
- [ ] 4.5 Run `openspec validate sign-in --type change` before archive
