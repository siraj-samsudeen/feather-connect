# record-trace

## Purpose
"Where is invoice 1001?" is the question an operator is asked most. A record can be followed by its business identity through every version and every destination, and two versions can be compared to see what changed.

## Requirements

### Requirement: Follow one record
The system SHALL show, for a record found by its business identity, every version it appeared in and what happened to it at each destination.

#### Scenario: An order's journey is shown

```gherkin
Given order 1001 was delivered to the warehouse and failed at the accounts service
When the user looks up order 1001
Then both destinations are shown with those outcomes
And the failure shows its error
```

### Requirement: Compare two versions
The system SHALL show which records were added, removed and changed between two versions of a slice, and which fields changed.

#### Scenario: A changed total is shown

```gherkin
Given order 1001 had a total of 200 in one version and 250 in the next
When the user compares the two versions
Then order 1001 is shown as changed, with its total going from 200 to 250
```
