# scheduling

## Purpose
A flow runs when it should: at set times, at a steady interval, when an event arrives, or when someone asks. Whatever happens, including a start that was skipped, is written down.

## Requirements

### Requirement: Run on a schedule
The system SHALL start a flow at set calendar times in a named time zone, or at a steady interval down to seconds.

#### Scenario: A flow runs at its time

```gherkin
Given the orders flow is set to run at six every morning in the shop's time zone
When it is six in the morning there
Then the orders flow runs
```

### Requirement: Run on request
The system SHALL start a flow when a user asks.

#### Scenario: A user runs a flow now

```gherkin
Given the orders flow is not due for an hour
When the user runs the orders flow now
Then the orders flow runs
```

### Requirement: Run when an event arrives
The system SHALL start a flow when an event it listens for arrives.

#### Scenario: An incoming order starts the flow

```gherkin
Given the orders flow listens for order events
When the shop sends order 1001
Then the orders flow delivers order 1001
```

### Requirement: Every start is recorded
The system SHALL record every start that was due, including one it skipped, with the reason.

#### Scenario: A skipped start is shown with its reason

```gherkin
Given the orders flow is paused
When its scheduled time passes
Then the run list shows a skipped start, saying the flow was paused
```

### Requirement: When the last run is still going
The system SHALL queue, skip or replace a start that comes due while the flow's last run is still going, as the flow says.

#### Scenario: By default the next run waits its turn

```gherkin
Given the orders flow's run is still going when the next is due
When the first run finishes
Then the next run starts
```

#### Scenario: A flow can skip instead

```gherkin
Given the orders flow says to skip a start while a run is going
When a start comes due during a run
Then that start is recorded as skipped, saying a run was still going
```

### Requirement: Catching up after downtime
The system SHALL catch up starts missed during downtime as one run, or one by one, as the flow says.

#### Scenario: One run covers the gap

```gherkin
Given the orders flow runs hourly and the product was down for three hours
When the product is back
Then the orders flow runs once, covering the three hours
```

### Requirement: Pause and resume
The system SHALL let the user pause and resume a flow, or a single destination.

#### Scenario: A paused destination catches up when resumed

```gherkin
Given the user has paused the accounts service route
And order 1001 has been read meanwhile
When the user resumes the route
Then order 1001 is delivered to the accounts service
```

### Requirement: Connection hours
The system SHALL keep to the hours a connection may be read or written, and make work that falls outside them wait in plain sight.

#### Scenario: A read waits for its hours

```gherkin
Given the shop database may be read only at night
When the orders flow is due at noon
Then its read is shown as waiting for the connection's hours
And it runs when the night hours open
```

#### Scenario: An event is kept at once while its destination is closed

```gherkin
Given the accounts service may be written only at night
When the shop sends order 1001 at noon
Then order 1001 is kept at once
And it is delivered when the night hours open
```

### Requirement: Frequent polls stay readable
The system SHALL show a flow that polls every few seconds as one run a day, with each poll inside it.

#### Scenario: A day of polls is one entry

```gherkin
Given the orders flow polls every thirty seconds
When the user looks at today's runs
Then the orders flow shows one run for today, holding its polls
```

### Requirement: One scheduler
The system SHALL start each due run exactly once, however many copies of the server are running.

#### Scenario: Two servers do not start a flow twice

```gherkin
Given two copies of the server are running
When the orders flow comes due
Then the orders flow runs once
```
