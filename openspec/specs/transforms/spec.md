# transforms

## Purpose
Each destination can receive the data in its own form. A transform changes, filters or enriches records on their way to one destination, without touching what the others receive.

## Requirements

### Requirement: Change or filter records for one destination
The system SHALL let each destination have its own rule that changes or leaves out records, one at a time or a batch at a time.

#### Scenario: One destination gets a reshaped order

```gherkin
Given the accounts service route renames the order total and leaves out cancelled orders
When order 1001 and the cancelled order 1002 are delivered
Then the accounts service receives order 1001 with the renamed total
And the warehouse receives both orders unchanged
```

#### Scenario: One order is split into its lines

```gherkin
Given the warehouse route splits each order into one record per line
When order 1001 with three lines is delivered
Then the warehouse receives three records for order 1001
```

### Requirement: Transform with a query
The system SHALL let a batch be transformed by a query written in SQL.

#### Scenario: A query adds a computed value

```gherkin
Given the warehouse route runs a query that adds the tax amount to each order
When order 1001 is delivered
Then the warehouse receives order 1001 with its tax amount
```

#### Scenario: A query cannot reach outside

```gherkin
Given a query on the warehouse route tries to read a file from the server's disk
When order 1001 is delivered
Then the delivery fails, saying the query may read only the batch and named datasets
```

### Requirement: Look up another dataset
The system SHALL let a transform look up the latest state of another dataset, and use one state of it throughout a delivery.

#### Scenario: An order is enriched with its customer

```gherkin
Given the warehouse route looks up each order's customer in the customers dataset
When order 1001 of customer 7 is delivered
Then the warehouse receives order 1001 with the name of customer 7
```

#### Scenario: A lookup that changes half-way does not split a delivery

```gherkin
Given a delivery of many orders has started
When the customers dataset gets a new version before the delivery ends
Then every order of that delivery uses the customers as they were when it started
And the next delivery uses the new version
```

#### Scenario: A missing lookup row is filled in by a replay

```gherkin
Given order 1001 was delivered before its customer existed in the customers dataset
When the customer arrives and the user replays that version
Then the warehouse receives order 1001 with the customer's name
```

### Requirement: A dataset made from other datasets
The system SHALL let a dataset be a query over other datasets, worked out again on a schedule and delivered like any other.

#### Scenario: A price is not delivered before its date

```gherkin
Given a price for an item is recorded to take effect on 1 November
And today's prices is a dataset worked out daily from the price list
When it is worked out on 31 October
Then the new price is not delivered
```

#### Scenario: A price is delivered once on its date

```gherkin
Given a price for an item is recorded to take effect on 1 November
And today's prices is a dataset worked out daily from the price list
When it is worked out on 1 November
Then the new price is delivered once
```
