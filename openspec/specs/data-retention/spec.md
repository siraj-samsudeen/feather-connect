# data-retention

## Purpose
The product keeps a great deal: what it read, what it delivered, logs, the audit trail. Each kind is kept for as long as it is useful and then cleared, so the database does not grow without end.

## Requirements

### Requirement: Each kind of data has its keeping time
The system SHALL keep each kind of data for its own set time and clear it afterwards: read data until every destination has taken it and some days more, the history of deliveries for months, the audit log for years.

#### Scenario: Old read data is cleared

```gherkin
Given a version was delivered everywhere longer ago than its keeping time
When clearing runs
Then that version's records are gone
And the fact that it was delivered can still be seen
```

#### Scenario: Data still needed is kept

```gherkin
Given a version has not yet been delivered to the accounts service
When clearing runs
Then that version's records are kept, however old
```

### Requirement: Keeping times can be changed
The system SHALL let an environment set its own keeping times.

#### Scenario: A longer keeping time is honoured

```gherkin
Given an environment keeps read data for sixty days
When clearing runs on a version delivered thirty days ago
Then that version's records are kept
```

### Requirement: Clearing is reported
The system SHALL say what each clearing removed.

#### Scenario: The user sees what was cleared

```gherkin
Given clearing has run
When the user looks at its result
Then it says how much of each kind of data was removed
```
