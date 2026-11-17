# connectors

## Purpose
A connector is what reaches one kind of system. The product ships general-purpose ones, and gives anyone the means to write their own, check it properly, and install it without changing the product.

## Requirements

### Requirement: Write a connector
The system SHALL let a developer write a connector that reads, writes or both, says what it can do and what settings it needs, checks itself, and lists what it offers.

#### Scenario: A new connector is used by a flow

```gherkin
Given a developer has written a connector for a stock system
When a flow reads from the stock system through it
Then the stock records are delivered
```

### Requirement: Connectors that ship with the product
The system SHALL ship connectors for a relational database, file storage, web services, plain web calls, incoming events, an analytics database, and one that works in memory.

#### Scenario: A table is read with no extra code

```gherkin
Given the shop database holds an orders table
When a flow names that table as its source
Then its orders are read
```

### Requirement: Say what a call costs
The system SHALL let a connector say what each call and each record costs against a budget, so a preview can estimate the cost of an action.

#### Scenario: A preview estimates the calls

```gherkin
Given the accounts service connector says each order costs one call
When the user previews a retry of twenty orders
Then the preview expects twenty calls
```

### Requirement: Check a connector properly
The system SHALL provide a check that a connector must pass before it is called beta or stable.

#### Scenario: A connector that repeats its work fails the check

```gherkin
Given a connector that writes a record twice when asked to write it again
When the check is run on it
Then the check fails, saying writing twice changed the result
```

### Requirement: Install someone else's connector
The system SHALL use a connector installed separately, without the product being changed.

#### Scenario: A separately installed connector is found

```gherkin
Given a connector for a stock system is installed on its own
When the user lists the connectors
Then the stock system connector is among them
```

### Requirement: Calling web services is built in
The system SHALL give every connector one way of calling web services that retries, counts against budgets and keeps secrets out of logs.

#### Scenario: A connector's calls count against the budget

```gherkin
Given a connector written with the built-in way of calling web services
And its connection has a budget
When it makes a call
Then the call is counted against that budget
```
