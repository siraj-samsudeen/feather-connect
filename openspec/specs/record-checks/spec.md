# record-checks

## Purpose
Bad records should not stop good ones. Records are checked against the shape a dataset declares; the ones that fail are set aside with the reason, where an operator can look at them, fix the cause and send them again.

## Requirements

### Requirement: Invalid records are set aside
The system SHALL set aside a record that does not match its dataset's declared shape, with the reason, and deliver the rest.

#### Scenario: One invalid order does not stop the others

```gherkin
Given the orders dataset says every order has a total
When order 1001 with a total and order 1002 without one are read
Then order 1001 is delivered
And order 1002 is set aside, saying the total is missing
```

### Requirement: Fail the whole version instead
The system SHALL fail the whole version when one record is invalid, where the flow asks for that.

#### Scenario: A strict flow delivers nothing

```gherkin
Given the orders flow says one invalid record fails the whole version
When order 1001 with a total and order 1002 without one are read
Then neither order is delivered
And the version is marked as failed with the reason
```

### Requirement: A record set aside is resolved by a newer one
The system SHALL mark a record set aside as replaced when a newer version of the same record is delivered.

#### Scenario: A corrected order clears the one set aside

```gherkin
Given order 1002 was set aside for a missing total
When order 1002 arrives again with a total and is delivered
Then the earlier order 1002 is marked as replaced
```
