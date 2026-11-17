# readiness

## Purpose
Some work should start only when the data it needs is all there. Readiness is the product knowing how far a dataset, or a group of datasets, is complete, so that a flow can wait for it without anything else being held up.

## Requirements

### Requirement: Know how far data is complete
The system SHALL track how far each dataset has been read, and how far each destination has received it.

#### Scenario: Read and delivered are shown apart

```gherkin
Given the orders of 18 October have been read but not yet delivered to the warehouse
When the user looks at the readiness of the orders dataset
Then it is read through 18 October
And delivered to the warehouse through 17 October
```

### Requirement: Start a flow when its data is ready
The system SHALL start a waiting flow once for each period when every dataset it needs is ready.

#### Scenario: A daily summary waits for all its inputs

```gherkin
Given the daily summary flow needs the orders and the payments of a day
And the orders of 18 October are ready but the payments are not
When the payments of 18 October become ready
Then the daily summary flow runs once for 18 October
```

### Requirement: Ready one part at a time
The system SHALL, where a flow asks for it, treat each value of a field as ready on its own.

#### Scenario: One shop does not wait for another

```gherkin
Given the daily summary flow is split by shop
And Shop 12 is ready for 18 October but Shop 13 is not
When readiness is checked
Then the daily summary runs for Shop 12
And waits for Shop 13
```

### Requirement: Waiting holds nothing else up
The system SHALL let readiness hold back only the flows that asked for it.

#### Scenario: Orders keep flowing while the summary waits

```gherkin
Given the daily summary flow is waiting for payments
When new orders arrive
Then the orders are delivered to the warehouse as usual
```

### Requirement: Data that arrives late
The system SHALL run the flow again, warn, or do nothing, as the flow says, when data arrives after its period has already run.

#### Scenario: A late order runs the summary again

```gherkin
Given the daily summary of 18 October has run
And the flow says late data runs it again
When another order dated 18 October arrives
Then the daily summary of 18 October runs once more
```

### Requirement: Not more often than asked
The system SHALL not start a waiting flow more often than the interval the flow sets.

#### Scenario: Two quick arrivals start one run

```gherkin
Given a flow that starts when orders are delivered, at most once every four hours
When orders are delivered twice within an hour
Then the flow starts once
```

### Requirement: Close a period by hand, or start now
The system SHALL let the user mark a period as complete by hand, and start a waiting flow now.

#### Scenario: The user closes a day the source never closed

```gherkin
Given the daily summary waits for payments of 18 October that will never arrive
When the user marks the payments of 18 October as complete
Then the daily summary flow runs for 18 October
```

### Requirement: See what a flow is waiting for
The system SHALL say what a waiting flow is waiting for.

#### Scenario: The missing input is named

```gherkin
Given the daily summary flow waits for the payments of Shop 13 on 18 October
When the user looks at the daily summary flow
Then it says it is waiting for the payments of Shop 13 through 18 October
```
