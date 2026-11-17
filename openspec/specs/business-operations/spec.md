# business-operations

## Purpose
Some deliveries are not just data: they do something in another system, such as posting a sale to a ledger. Those must never happen twice, must be reversible, and may need a person's approval first.

## Requirements

### Requirement: An operation is never done twice
The system SHALL carry out a business operation once, even when a process stops in the middle of it.

#### Scenario: A sale is posted once

```gherkin
Given the day's sales of Shop 12 are being posted to the ledger
When the process posting them is stopped half-way and the work resumes
Then the ledger holds each sale once
```

### Requirement: Reverse an operation
The system SHALL let the user reverse a delivered business operation.

#### Scenario: A posted day is reversed

```gherkin
Given the sales of Shop 12 on 18 October were posted to the ledger
When the user reverses that delivery
Then the ledger shows those postings reversed
And the delivery is marked as reversed
```

### Requirement: Approval before delivery
The system SHALL hold records for a person's approval where a destination asks for it: always, in some environments, or for records that meet a condition.

#### Scenario: A large sale waits, the rest go on

```gherkin
Given the ledger route needs approval for a sale above 5,000
When sales of 200 and of 8,000 are due
Then the sale of 200 is posted
And the sale of 8,000 waits for approval
```

#### Scenario: Approval only in production

```gherkin
Given the ledger route needs approval in production only
When a sale is due in the test environment and in production
Then it is posted in the test environment
And it waits for approval in production
```

### Requirement: Decide a hold
The system SHALL let a user who may decide holds approve or reject one, with a reason.

#### Scenario: An approved sale is posted

```gherkin
Given the sale of 8,000 waits for approval
When an approver approves it with a reason
Then the sale of 8,000 is posted to the ledger
```

#### Scenario: A rejected sale is not posted

```gherkin
Given the sale of 8,000 waits for approval
When an approver rejects it with a reason
Then the sale is not posted
And it is marked as skipped with that reason
```

#### Scenario: A user without the right cannot decide

```gherkin
Given the sale of 8,000 waits for approval
When a user who may not decide holds tries to approve it
Then the request is refused
```
