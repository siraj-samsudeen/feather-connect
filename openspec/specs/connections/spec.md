# connections

## Purpose
A connection is one system set up in one environment: its address, its settings and its secrets. An operator can check that it works, and change it, without touching a flow's code.

## Requirements

### Requirement: Test a connection
The system SHALL check on request that a connection can reach its system, and say what is wrong when it cannot.

#### Scenario: A working connection passes

```gherkin
Given the accounts service connection is set up correctly
When the user tests it
Then the test passes
```

#### Scenario: A broken connection says why

```gherkin
Given the accounts service connection has a wrong address
When the user tests it
Then the test fails, saying the address could not be reached
```

### Requirement: Change a connection's settings
The system SHALL show a connection's settings that are not secret, let a user with the right change them, and record each change with the old and the new value.

#### Scenario: A changed address is recorded

```gherkin
Given the accounts service connection points to one address
When an administrator changes it to another
Then deliveries use the new address
And the audit log shows the old and the new address
```

### Requirement: Replace a secret
The system SHALL let a user with the right replace or remove a connection's secret, and never show a secret once it is set.

#### Scenario: A replaced secret is used and stays hidden

```gherkin
Given the accounts service connection has a password set
When an administrator replaces the password
Then deliveries use the new password
And the password is not shown anywhere
```
