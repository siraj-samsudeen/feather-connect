# monitoring-dashboard

## Purpose
One place shows whether everything is healthy and, when it is not, where and why. An operator starts at an overview and can go down to a single flow, slice, run or delivery without a command line.

## Requirements

### Requirement: Overview of health
The system SHALL show on one page what needs attention: failures, datasets that are out of date, budgets nearly used up, work waiting for a decision, alerts, and whether workers are running.

#### Scenario: A failure shows on the overview

```gherkin
Given the delivery of order 1001 to the accounts service has failed
When the user opens the overview
Then it shows one failing delivery
And the user can go from it to that delivery
```

### Requirement: Flows and their detail
The system SHALL list the flows and show, for each, a picture from its sources to its destinations, its settings and where each came from, and the version of the code it runs.

#### Scenario: A flow's page shows where its data goes

```gherkin
Given the orders flow reads the shop database and delivers to the warehouse and the accounts service
When the user opens the orders flow
Then the picture shows the shop database leading to both destinations
And the version of the code it runs is shown
```

### Requirement: Slices over time
The system SHALL show, for every dataset, each slice and each destination over time, with its state, and let the user open any of them.

#### Scenario: A failed slice stands out

```gherkin
Given the orders of Shop 12 on 18 October failed at the accounts service and succeeded at the warehouse
When the user looks at the slices of the orders dataset
Then that slice shows as failed for the accounts service and delivered for the warehouse
```

### Requirement: Slices in business words
The system SHALL name a slice in business words.

#### Scenario: A slice reads as a shop and a day

```gherkin
Given the orders dataset is sliced by shop and day
When the user looks at its slices
Then the slice of Shop 12 on 18 October is named by its shop and its date
```

### Requirement: Runs and their steps
The system SHALL show each run with its steps over time, what it was asked to do, its log, its tries, and the records each step read or wrote.

#### Scenario: A run shows what it read

```gherkin
Given a run of the orders flow read order 1001
When the user opens that run
Then its reading step lists order 1001
And the step's log can be read on the same page
```

### Requirement: Deliveries and failures
The system SHALL list every delivery with its state, and group failures by their error.

#### Scenario: Failures with one cause are grouped

```gherkin
Given twenty deliveries to the accounts service failed with the same error
When the user looks at the failures
Then they are shown as one group of twenty with that error
```

### Requirement: Pages for what an operator looks after
The system SHALL give a page each to records set aside, work waiting for a decision, budgets, readiness, connections, secrets, packages, users, and a search across them.

#### Scenario: Search finds a flow by name

```gherkin
Given the orders flow exists
When the user searches for "orders"
Then the orders flow is among the results
```

### Requirement: Every view can be shared
The system SHALL give every view, with its filters, an address that shows the same view to anyone who may see it.

#### Scenario: A filtered list is shared

```gherkin
Given the user has filtered the failures to the accounts service
When a colleague opens the address the user copied
Then the colleague sees the failures filtered to the accounts service
```

### Requirement: Workers
The system SHALL show the workers that are connected, the version of the code each runs, and when each was last heard from.

#### Scenario: A stopped worker is seen to be gone

```gherkin
Given two workers are connected
When one of them stops
Then the workers shown fall to one
```

### Requirement: A run says why it delivered nothing
The system SHALL say, for a run that delivered nothing, why: nothing had changed, the flow was paused, or it was waiting.

#### Scenario: Nothing had changed

```gherkin
Given the orders flow ran and found nothing changed at the source
When the user opens that run
Then it says nothing was delivered because nothing had changed
```

### Requirement: Where you are and who you are
The system SHALL show on every page which environment it is and who is signed in, with which role.

#### Scenario: The environment and the user are always shown

```gherkin
Given an operator is signed in to the test environment
When the operator opens the list of flows
Then the page shows the test environment and the operator's name and role
```

#### Scenario: A problem with the database is shown on every page

```gherkin
Given the operator has the list of flows open
When the database cannot be reached
Then the page shows that the database is not well
```

### Requirement: What the destination answered
The system SHALL show, for each delivery, every attempt and what the destination answered for each record, with secrets removed.

#### Scenario: The destination's answer is shown

```gherkin
Given the accounts service answered order 1001 with its own reference A-77
When the user opens that delivery
Then the answer for order 1001 shows A-77
```

### Requirement: Two versions of the code at once
The system SHALL flag a flow that is running on two versions of the code at once.

#### Scenario: A flow on two versions is flagged

```gherkin
Given one worker runs the orders flow on version 1.4 and another on version 1.5
When the user opens the orders flow
Then it is flagged as running on two versions
```
