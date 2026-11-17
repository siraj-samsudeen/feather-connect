# durable-execution

## Purpose
Work that has been accepted is never lost and never done twice, whatever stops in the middle: a process, the database, the network. And nothing fails without a trace.

## Requirements

### Requirement: Accepted work survives a crash
The system SHALL lose no accepted work when any of its processes is stopped without warning.

#### Scenario: A delivery survives its worker being stopped

```gherkin
Given order 1001 is being delivered to the warehouse
When the process delivering it is stopped without warning
Then order 1001 still reaches the warehouse
And it is there once
```

#### Scenario: Work survives a database restart

```gherkin
Given the orders flow is in the middle of a run
When the database restarts
Then the run completes
And no order is lost or delivered twice
```

### Requirement: Retry a failed call
The system SHALL try a failed call again after growing waits, honouring a wait the other system asks for, up to a limit.

#### Scenario: A brief outage heals itself

```gherkin
Given the accounts service fails for a minute
When order 1001 is delivered during that minute
Then the delivery is tried again
And order 1001 is delivered once the service is back
```

#### Scenario: A lasting outage ends as a failure

```gherkin
Given the accounts service stays down
When the tries for order 1001 are used up
Then the delivery is marked as failed with the last error
```

### Requirement: Nothing fails silently
The system SHALL record every delivery and its outcome, with the reason when it did not succeed.

#### Scenario: A failed delivery can be found

```gherkin
Given the delivery of order 1001 to the accounts service failed
When the user looks at the failures
Then that delivery is listed with its error
```

### Requirement: A half-done operation resumes
The system SHALL resume an interrupted delivery without repeating the part already done.

#### Scenario: Three of ten are not sent again

```gherkin
Given ten orders are being posted to the accounts service and three are done
When the process is stopped and the delivery resumes
Then the remaining seven are posted
And the first three are not posted again
```

### Requirement: Lost data is marked, not hidden
The system SHALL mark a version whose kept data is gone after a restore as lost.

#### Scenario: A version missing after a restore is marked

```gherkin
Given the database was restored to an hour ago
And a version read since then has no kept data
When the product starts
Then that version is marked as lost
And the user can read its slice again
```

### Requirement: New code in the middle of work
The system SHALL lose nothing and deliver nothing twice when a new version of the code is put in place while deliveries are in progress.

#### Scenario: A deploy during a delivery

```gherkin
Given orders are being delivered
When a new version of the product is put in place
Then every order is delivered once
```
