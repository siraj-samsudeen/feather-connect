# personal-data

## Purpose
Records often hold personal details. Fields marked as personal are hidden wherever data is shown, and only people given the right can reveal them, with a trace each time.

## Requirements

### Requirement: Personal fields are masked
The system SHALL hide the fields a dataset marks as personal wherever its records are shown: on the dashboard, in answers to programs and on the command line.

#### Scenario: An email address is hidden

```gherkin
Given the orders dataset marks the customer's email as personal
When the user looks at order 1001
Then the email is masked
And the order number and total are shown
```

### Requirement: Revealing needs the right and is recorded
The system SHALL reveal a personal field only to a user granted that right, and record each time it is revealed.

#### Scenario: A user without the right cannot reveal

```gherkin
Given a user without the right to see personal data
When that user asks to reveal the email of order 1001
Then the request is refused
```

#### Scenario: Revealing leaves a trace

```gherkin
Given a user with the right to see personal data
When that user reveals the email of order 1001
Then the email is shown
And the audit log records that the user revealed it
```
