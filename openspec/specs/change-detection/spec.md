# change-detection

## Purpose
A flow should deliver only what changed. This is how a dataset finds out which records are new, changed or gone since the last time it was read.

## Requirements

### Requirement: Find changes by a change stamp
The system SHALL read only records changed since the last read, looking back a set time, when the source marks each record with the time it changed.

#### Scenario: Only the changed order is read

```gherkin
Given the orders dataset has been read once
And order 1001 is changed at the source afterwards
When the orders flow runs again
Then only order 1001 is delivered
```

#### Scenario: A record that became visible late is still caught

```gherkin
Given order 1002 becomes visible at the source with a change time inside the look-back
When the orders flow runs again
Then order 1002 is delivered once
```

### Requirement: Find changes by comparing a slice
The system SHALL find added, changed and deleted records by comparing a whole slice with the last read of it, for sources with no change stamp.

#### Scenario: A deleted record is found

```gherkin
Given the orders of Shop 12 on 18 October were read with order 1001 among them
And order 1001 is deleted at the source
When that slice is read again
Then order 1001 is removed at the warehouse
```

### Requirement: Reload a slice
The system SHALL let a dataset be reloaded a whole slice at a time, where reloading is simpler than comparing.

#### Scenario: The slice is delivered whole

```gherkin
Given the price list is a dataset that is reloaded whole
When the prices flow runs
Then every price of the list is delivered
```

### Requirement: Events pushed in
The system SHALL take records pushed to it as events, and deliver them without waiting for a schedule.

#### Scenario: A pushed order is delivered

```gherkin
Given the orders dataset takes events
When the shop sends order 1001 as an event
Then order 1001 is delivered within seconds
```

### Requirement: Catch what a change stamp missed
The system SHALL compare a dataset read by change stamp in full on a schedule, to catch records the stamp missed.

#### Scenario: A back-dated record is caught

```gherkin
Given order 1003 is added at the source with a change time older than the last read
When the scheduled full comparison runs
Then order 1003 is delivered
```

### Requirement: Unchanged records are not sent again
The system SHALL not deliver a record again when it has not changed since it was last seen.

#### Scenario: Reading the same data twice delivers nothing

```gherkin
Given the orders of Shop 12 on 18 October have been delivered
When that slice is read again with nothing changed
Then nothing is delivered
```

### Requirement: An empty answer cannot wipe a destination
The system SHALL fail a full read that returns nothing, unless the dataset says an empty slice is allowed.

#### Scenario: An empty read fails

```gherkin
Given the orders of Shop 12 on 18 October hold twenty orders at the warehouse
When a full read of that slice returns nothing
Then the read fails
And the twenty orders stay at the warehouse
```

### Requirement: Deletes are decided after every slice is read
The system SHALL decide which records were deleted only after every slice of a run has been read, so a record that moved is not taken for a deleted one.

#### Scenario: A moved record is not deleted

```gherkin
Given order 1001 was read in the slice of 18 October
And its date is changed to 19 October at the source
When one run reads both slices
Then order 1001 is updated, not deleted and created again
```

### Requirement: An interrupted read resumes
The system SHALL resume a long read from where it had got to when it is interrupted.

#### Scenario: A read continues after an interruption

```gherkin
Given a read of ten thousand orders is interrupted half-way
When the read is taken up again
Then it continues from where it stopped
And every order is delivered once
```
