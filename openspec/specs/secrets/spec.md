# secrets

## Purpose
Passwords and keys are needed to reach other systems, and must never leak. A flow only ever names a secret; the product fetches it when needed and keeps it out of every page, log and message.

## Requirements

### Requirement: Secrets are named, never shown
The system SHALL let settings refer to a secret by name, and never show a secret's value on a page, in a log, or in an answer.

#### Scenario: A connection shows that a secret is set, not what it is

```gherkin
Given the accounts service connection uses a password kept as a secret
When the user looks at that connection
Then it shows that a password is set
And the password itself is not shown
```

### Requirement: Where secrets come from
The system SHALL take a secret from the machine's environment, from a file, or from its own store, where it is kept encrypted with a key held outside the database.

#### Scenario: A stored secret is used by a delivery

```gherkin
Given an administrator has stored the accounts service password
When order 1001 is delivered to the accounts service
Then the delivery signs in with that password
```

### Requirement: Secrets are cleaned from errors
The system SHALL remove secrets from an error message before it is kept or shown.

#### Scenario: An error that quotes a password is cleaned

```gherkin
Given the accounts service answers a failed sign-in with a message that repeats the password
When that failure is shown to the user
Then the password is replaced in the message
```
