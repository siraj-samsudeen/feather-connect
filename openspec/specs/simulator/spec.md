# simulator

## Purpose
Real systems are slow to get, costly to call and hard to make misbehave. The simulator stands in for any of them, with data that repeats exactly and faults that happen on purpose, for demos, tests and practice.

## Requirements

### Requirement: Stand in for a source
The system SHALL provide a stand-in source that gives records from a file, or makes them up from a description, the same way every time.

#### Scenario: Made-up data repeats

```gherkin
Given a stand-in source that makes up one hundred orders from a description
When it is read twice
Then both reads give the same one hundred orders
```

### Requirement: Stand in for a destination
The system SHALL provide a stand-in destination that keeps what it received, so a test can check it.

#### Scenario: A test reads what was delivered

```gherkin
Given the orders flow delivers to a stand-in destination
When order 1001 is delivered
Then a test can find order 1001 in what the stand-in received
```

### Requirement: Misbehave on purpose
The system SHALL let the stand-in misbehave on request: send a record twice, send one late, refuse a call, fail, answer slowly, drop the line, or say a limit is reached.

#### Scenario: A refused call is retried and succeeds

```gherkin
Given the stand-in accounts service is told to refuse the next call
When order 1001 is delivered
Then the first try is refused
And order 1001 is delivered on a later try
```

#### Scenario: A record sent twice is delivered once

```gherkin
Given the stand-in source is told to give order 1001 twice
When the orders flow runs
Then order 1001 is delivered once
```

#### Scenario Outline: Each fault is survived

```gherkin
Given the stand-in accounts service is told to <fault> on the next call
When order 1001 is delivered
Then order 1001 is delivered once in the end

Examples:
  | fault |
  | fail |
  | answer slowly |
  | drop the line |
  | say its limit is reached |
```
