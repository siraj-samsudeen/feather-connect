# deployment-and-upgrades

## Purpose
Running the product for real should be boring: a small, fixed set of parts, upgrades that do not stop work, more capacity by adding workers, and a backup that has been proved to restore.

## Requirements

### Requirement: A small production setup
The system SHALL run in production as at most four parts on one machine, needing one database and no cluster manager.

#### Scenario: The standard setup runs a flow

```gherkin
Given the product is started on one machine from its standard setup
When the orders flow is installed and switched on
Then orders are delivered
```

### Requirement: Upgrade without stopping work
The system SHALL be upgraded to a new version without work being lost or stopped.

#### Scenario: Deliveries carry on through an upgrade

```gherkin
Given orders are being delivered
When the product is upgraded to its next version
Then deliveries carry on
And no order is lost or delivered twice
```

### Requirement: More capacity by adding workers
The system SHALL do more work at once when another worker is started.

#### Scenario: A second worker shares the work

```gherkin
Given one worker is delivering a long backlog
When a second worker is started
Then both workers deliver from the backlog
```

### Requirement: A worker finishes before it stops
The system SHALL let a worker asked to stop finish what it is doing first.

#### Scenario: A stopping worker completes its delivery

```gherkin
Given a worker is delivering order 1001
When the worker is asked to stop
Then order 1001 is delivered before the worker stops
```

### Requirement: Restore from a backup
The system SHALL be restorable from a backup to a working state, losing at most five minutes of work and within one hour.

#### Scenario: A restored environment carries on

```gherkin
Given a backup of the environment exists
When the environment is restored from it
Then flows run again
And work accepted up to five minutes before the failure is still there
```
