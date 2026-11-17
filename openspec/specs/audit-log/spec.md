# audit-log

## Purpose
Every change is written down: who did it, what, when and why. The record cannot be altered, so it can be trusted when something has gone wrong.

## Requirements

### Requirement: Every action is recorded
The system SHALL record every change made by a person, a program or the product itself, with who made it, what was changed, when, and the reason given.

#### Scenario: A skip is recorded with its reason

```gherkin
Given the user skips a failed delivery, giving a reason
When the user opens the audit log
Then an entry shows the user, the delivery, the time and the reason
```

#### Scenario: The product's own actions are recorded too

```gherkin
Given the product has marked a version as lost after a restore
When the user opens the audit log
Then an entry shows that the product did it
```

### Requirement: The record cannot be changed
The system SHALL offer no way to change or remove an entry of the audit log.

#### Scenario: An administrator cannot remove an entry

```gherkin
Given an entry exists in the audit log
When an administrator looks for a way to change or remove it
Then there is none
```

### Requirement: Find an entry
The system SHALL let the user narrow the audit log by who acted, by the kind of action, and by the item acted on.

#### Scenario: The entries of one user are shown

```gherkin
Given two users have each skipped a delivery
When the user narrows the audit log to the first of them
Then only that user's entries are shown
```
