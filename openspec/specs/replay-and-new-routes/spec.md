# replay-and-new-routes

## Purpose
History that is still kept can be sent again. This lets an operator repair a destination that lost data, and lets a destination added later catch up with what the others already have.

## Requirements

### Requirement: Replay a kept version
The system SHALL send any version it still keeps to a destination again on request.

#### Scenario: A lost day is restored

```gherkin
Given the warehouse has lost the orders of Shop 12 on 18 October
When the user replays that slice to the warehouse
Then the warehouse holds those orders again
```

#### Scenario: A version no longer kept cannot be replayed

```gherkin
Given a version is past its keeping time
When the user asks to replay it
Then the request is refused, saying the version is no longer kept
```

#### Scenario: An older version cannot overwrite a newer one

```gherkin
Given the warehouse holds the latest version of Shop 12 on 18 October
When the user asks to replay an earlier version of that slice
Then the request is refused, naming the latest version
```

### Requirement: A new destination catches up
The system SHALL first send a destination added to a running flow the latest state of every slice, and then keep it up to date.

#### Scenario: A destination added later receives the history

```gherkin
Given the orders flow has delivered a month of orders to the warehouse
When a reporting database is added as a second destination
Then the reporting database receives that month of orders
And afterwards it receives each new order as the warehouse does
```
