---
name: security-baseline
description: "Use when a change touches sign-in, sessions, permissions, personal data, money, secrets or anything a person or another system sends in. Adds a short threat check to design.md and a checklist the build and the code review follow."
---

# Security baseline

Security is designed in, not reviewed in at the end. A change that touches any of these takes
this skill: sign-in or sessions, who may do what, personal data, money, secrets, files people
upload, or input from a person or another system.

## 1. The threat check, in `design.md`

A short section, **Threats**, of three to eight lines. For each way the change could be misused:

- **who** could do it (a stranger on the internet, a signed-in user of another tenant, a user
  with less permission, a compromised outside system);
- **what** they would try (read someone else's data, act as someone else, guess a password, send
  a request from another site, upload a script, exhaust a resource);
- **what stops them**, in this change, and the test that proves it.

A threat that nothing stops yet is either fixed in this change or written in the PR's
"Deliberately not handled", with the owner's agreement.

## 2. The checklist

The build follows it; the code review checks it (`AGENTS.md` § Review guidelines). Each line that
applies has a test.

| Area | Rule |
|---|---|
| Permissions | Every route and action checks who may do it, on the server, **denied by default**. One rights check in one place, not a condition in each page. A user of one tenant never reaches another tenant's data. |
| Input | Checked at the edge: type, length, format, allowed values. Rejected with a message that says what is wrong, never echoed back unescaped. |
| Output | Escaped by the template engine; no raw HTML from data. Database queries take parameters, never strings joined with input. |
| Sign-in and sessions | Passwords hashed with a slow algorithm (argon2id, scrypt or bcrypt); the same refusal, in the same time, for a wrong name and a wrong password; repeated failures slowed; a new session id at sign-in; sessions that can be ended from the server. |
| Forms and cookies | A token against forged requests on every form that changes something; cookies `HttpOnly`, `Secure` and `SameSite`. |
| Headers | A content policy with no inline script, `X-Content-Type-Options`, and a frame policy. |
| Secrets | From the environment, never in git, never in a log line, an error message, an audit record or a response. |
| Limits | Rate limits on sign-in and on anything costly; size limits on uploads and request bodies; timeouts on every call to another system. |
| Redirects | Only to this site's own paths: a `next=` parameter never leads elsewhere. |
| Audit | Sign-ins, refusals, permission changes and other security events are recorded, without secrets. |
| Dependencies | Audited in CI; each new one comes with an ADR (`change-modes` § Defaults). |

## 3. When it is not enough

Payments, health data, or anything regulated: propose an adversarial review in one line, with
the reason (`AGENTS.md` § Review guidelines), and say which standard applies.
