# backfill

## Purpose
Sometimes a whole range has to be read again: a new flow needs last year's data, or a source was wrong for a week. A backfill does that in business terms, shown before it runs and kept within limits.

## Requirements

### Requirement: Preview a backfill
The system SHALL show what a backfill will read and what it is expected to cost against call budgets, before it runs.

#### Scenario: The preview lists the slices

```gherkin
Given the user asks to backfill the orders of Shop 12 for the first week of October
When the preview is shown
Then it lists the seven slices to be read
And nothing has been read yet
```

### Requirement: Run a backfill within limits
The system SHALL run a backfill over the range asked for, keeping to the limits on work in parallel and on calls.

#### Scenario: A confirmed backfill reads the range

```gherkin
Given the user has seen the preview for the first week of October
When the user confirms it
Then the seven slices are read and delivered
And the scheduled runs of the orders flow carry on meanwhile
```
