# call-budgets

## Purpose
Many systems limit how often they may be called, and every flow that calls one shares that limit. A call budget is that limit, named once and shared out, so that it is never broken and important work keeps its share.

## Requirements

### Requirement: A shared limit is never exceeded
The system SHALL count every call that every flow makes to a system against that system's budget, and never exceed it.

#### Scenario: Two flows share one limit

```gherkin
Given the accounts service allows 100 calls a minute
And two flows call the accounts service
When both are busy
Then together they make no more than 100 calls in any minute
```

### Requirement: Several windows at once
The system SHALL keep to several limits on the same system at once, such as one a minute and one a day.

#### Scenario: The daily limit holds as well

```gherkin
Given the accounts service allows 100 calls a minute and 10,000 a day
When 10,000 calls have been made today
Then no further call is made until tomorrow
```

### Requirement: A share kept for important work
The system SHALL keep a set share of a budget for high-priority work.

#### Scenario: Low-priority work stops short of the limit

```gherkin
Given 60 calls in every 100 are kept for high-priority work
And a low-priority flow is busy
When the low-priority flow has used 40 calls this minute
Then it waits
And a high-priority flow can still call
```

### Requirement: Running out is a wait, not a failure
The system SHALL make work wait, in plain sight, when a budget is used up, and carry on when the budget refills.

#### Scenario: Work waits for tomorrow's budget

```gherkin
Given today's budget for the accounts service is used up
When order 1001 is due for delivery there
Then the delivery is shown as waiting for the budget until tomorrow
And it is delivered tomorrow without anyone acting
```

### Requirement: See how a budget is used
The system SHALL show each budget's limits, its use, the share kept back, and the work waiting on it.

#### Scenario: The user sees who is waiting

```gherkin
Given three deliveries wait for the accounts service budget
When the user looks at that budget
Then its use today and the three waiting deliveries are shown
```

### Requirement: A read that can never fit fails at once
The system SHALL fail a read that could never fit within its budget, naming the budget, instead of waiting for ever.

#### Scenario: A read bigger than a whole day's budget

```gherkin
Given the accounts service allows 1,000 calls a day
When a read needs 5,000 calls before it can finish
Then the read fails, naming the accounts service budget
```
