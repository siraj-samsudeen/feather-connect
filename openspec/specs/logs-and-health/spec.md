# logs-and-health

## Purpose
When something needs investigating, the trail is already there, and when the product itself is unwell, an outside monitor can tell. Neither needs extra systems to be installed.

## Requirements

### Requirement: Logs that can be followed
The system SHALL write its log so that every line about a piece of work names the flow, the run, the slice and the destination it belongs to.

#### Scenario: The lines of one run can be picked out

```gherkin
Given two runs of the orders flow happened at the same time
When the user asks for the log of one of them
Then only that run's lines are shown
```

### Requirement: Logs and charts without extra systems
The system SHALL show a step's log and the dashboard's charts from what it keeps itself.

#### Scenario: A step's log is on its page

```gherkin
Given a run of the orders flow has finished
When the user opens one of its steps
Then that step's log is shown there
```

### Requirement: Health an outside monitor can check
The system SHALL answer, at fixed addresses, whether it is running and whether it is ready to take work.

#### Scenario: Not ready while the database is away

```gherkin
Given the product is running
When the database cannot be reached
Then the product answers that it is running but not ready
```
