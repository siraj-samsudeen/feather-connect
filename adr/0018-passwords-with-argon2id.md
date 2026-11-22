# 0018. Passwords are hashed with argon2id, and repeated failures are slowed, never locked

- Status: accepted
- Date: 2026-11-22
- Decision-makers: the project owner
- Decided in: issue #16, points 3 and 7

## Context and Problem Statement

Users sign in with a password (R10.1), and repeated failures must be slowed by user and by
address (R10.12). A stored hash must hold up if the database is copied, and a sign-in must stay
cheap enough for a small machine. Once hashes are stored, changing the method means rehashing at
each user's next sign-in.

## Considered Options

- argon2id through `argon2-cffi`, at OWASP's recommended strength (19 MiB, 2 passes), its
  settings stored with each hash.
- scrypt, from Python's standard library.
- bcrypt.

## Decision Outcome

Chosen option: "argon2id", because it is the method OWASP recommends first, resists guessing on
graphics cards by needing memory, and is cheap at that strength: measured on a developer's
machine, 34 ms and 19 MB per sign-in, against 2,243 ms and 128 MB for scrypt at its recommended
strength. A hash is redone at the next sign-in when the settings rise. A password has 12 to 128
characters of any kind, no composition rules, and is refused if it is very common or the user's
own name. After 3 failed sign-ins in 15 minutes, for one name from any address or from one
address for any name, each further attempt waits: 1 s, 2 s, 4 s and so on, up to a minute,
counted in the database so it holds across server copies. No account is ever locked, and every
refusal uses the same words and takes the same time.

### Consequences

- Good, because a copied database's hashes are slow and costly to guess, and a sign-in stays
  fast.
- Good, because nobody can lock out a user, the administrator included, by guessing wrong on
  purpose.
- Bad, because `argon2-cffi` is a new dependency with compiled code (wheels exist for Python
  3.14 on every platform the image and CI use).
- Bad, because a guesser can still try about one name a minute per address after the first
  three; long passwords and the common-password list are what make that useless.
- Rejected: scrypt, sixty times slower and seven times the memory at its recommended strength;
  bcrypt, which cuts passwords at 72 bytes and needs no memory to guess; locking accounts, which
  lets an attacker lock out anyone; a CAPTCHA, which needs a third party or scripts.
