# environments

## Purpose
The same product runs as separate environments: one to develop in, one or more to test in, one for real work. Each has its own data and settings, and the one that matters has extra safeguards against mistakes.

## Requirements

### Requirement: Environments are separate
The system SHALL keep each environment's data, connections, secrets and settings apart from every other's.

#### Scenario: A change in test does not reach production

```gherkin
Given the orders flow runs in the test environment and in production
When the user pauses it in the test environment
Then it keeps running in production
```

### Requirement: A reason for every change where it matters
The system SHALL ask for a reason before any change in a protected environment, and show that the environment is protected.

#### Scenario: A retry without a reason is refused

```gherkin
Given production is a protected environment
When the user retries a delivery there without giving a reason
Then the request is refused, asking for a reason
```

#### Scenario: A retry with a reason goes through

```gherkin
Given production is a protected environment
When the user retries a delivery there with a reason
Then the delivery is retried
And the reason is in the audit log
```

### Requirement: A second person for what cannot be undone
The system SHALL make an action that cannot be undone in a protected environment wait for a second person to approve it.

#### Scenario: A mass skip waits for someone else

```gherkin
Given production is a protected environment
When the user asks to skip twenty failed deliveries there
Then the request waits for approval
And the user who asked cannot approve it
```

### Requirement: Read-only by default where it matters
The system SHALL make a token created in a protected environment able only to look, unless more is asked for.

#### Scenario: A new token cannot change anything

```gherkin
Given production is a protected environment
When an administrator creates a token there without choosing its rights
Then that token can look at flows and cannot retry a delivery
```

### Requirement: Test on stand-in systems
The system SHALL let a development or test environment run its flows against stand-in systems instead of real ones.

#### Scenario: The test environment calls nothing real

```gherkin
Given the test environment is set to use stand-in systems
When the orders flow runs there
Then orders are delivered to the stand-in warehouse
And the real warehouse is not called
```

### Requirement: Several test environments on one machine
The system SHALL let several test environments run on one machine, each with its own data.

#### Scenario: Two test environments do not share data

```gherkin
Given two test environments run on one machine
When the orders flow delivers order 1001 in the first
Then the second shows no delivery of order 1001
```
