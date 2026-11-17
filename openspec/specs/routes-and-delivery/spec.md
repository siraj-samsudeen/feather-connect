# routes-and-delivery

## Purpose
One dataset can go to many destinations. Each destination is a route with its own progress, so a slow or broken one never holds the others up, and each receives every version once and in order.

## Requirements

### Requirement: One dataset, many destinations
The system SHALL deliver one dataset to any number of destinations, each moving on, failing and recovering on its own.

#### Scenario: One destination down does not stop the other

```gherkin
Given the orders flow delivers to the warehouse and to the accounts service
And the accounts service is down
When order 1001 is read
Then order 1001 reaches the warehouse
And its delivery to the accounts service waits
```

### Requirement: Reading never waits for a destination
The system SHALL keep what was read safely before delivering it, so a destination being down cannot lose a read.

#### Scenario: A read completes while every destination is down

```gherkin
Given every destination of the orders flow is down
When the orders flow reads order 1001
Then the read completes
And order 1001 is delivered once the destinations are back
```

### Requirement: Versions are applied in order
The system SHALL apply the versions of a slice to a destination in the order they were made.

#### Scenario: A later change does not overtake an earlier one

```gherkin
Given order 1001 is changed twice and the first change fails at the accounts service
When the second change is ready
Then it waits until the first has been applied or skipped
```

### Requirement: Each version takes effect once
The system SHALL make each version take effect at each destination exactly once, even when a process stops in the middle.

#### Scenario: An interrupted delivery is not repeated

```gherkin
Given order 1001 is being delivered to the accounts service
When the process delivering it is stopped half-way and the delivery is taken up again
Then the accounts service holds order 1001 once
```

### Requirement: Ways of writing
The system SHALL let a route update records by their identity, add every change as history, or replace a whole slice at once.

#### Scenario: Updating by identity keeps one row

```gherkin
Given the warehouse route updates by order number
When order 1001 is delivered, changed and delivered again
Then the warehouse holds one row for order 1001 with the latest values
```

#### Scenario: Adding as history keeps every change

```gherkin
Given the warehouse route adds every change as history
When order 1001 is delivered, changed and delivered again
Then the warehouse holds two rows for order 1001
```

### Requirement: A newer whole document can replace a failed older one
The system SHALL, where a route asks for it, let a newer version of a whole document take the place of an older version that failed.

#### Scenario: The newer order replaces the failed one

```gherkin
Given a delivery of order 1001 failed at the accounts service
And the route lets a newer document replace a failed one
When a newer version of order 1001 arrives
Then the newer version is delivered
And the failed one is marked as replaced
```

### Requirement: One writer at a time
The system SHALL let one delivery at a time write a slice to a destination, unless the route allows more.

#### Scenario: Two versions of one slice are not written together

```gherkin
Given two versions of Shop 12 on 18 October wait for the warehouse
When delivery starts
Then the second is written only after the first has finished
```

### Requirement: A problem stops only its own slice
The system SHALL set aside a single record that cannot be delivered and carry on with the rest, and stop only that slice on that destination when the whole version cannot be delivered.

#### Scenario: One bad record does not stop the others

```gherkin
Given a version holds orders 1001 and 1002, and the accounts service turns order 1002 down
When the version is delivered
Then order 1001 is delivered
And order 1002 is set aside with the reason
```

#### Scenario: A refused sign-in stops one slice only

```gherkin
Given the accounts service refuses the sign-in
When versions of Shop 12 and of Shop 13 are due
Then deliveries to the accounts service fail and wait
And deliveries of both shops to the warehouse carry on
```
