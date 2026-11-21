# Logs and health

## Purpose

The host the product runs on (the service that starts it and restarts it), or an uptime monitor
(a service that checks a site every minute or so), can tell whether the product is running and
whether it is ready to take work. Ready means the product can use its database.

## Requirements

### Requirement: Health an outside monitor can check
The system SHALL answer, at fixed addresses open to any monitor, whether it is running and whether it is ready to take work, without saying where its database is or what went wrong with it.

#### Scenario: Running and ready

```gherkin
Given the product is running with its database
When a monitor checks it
Then the product answers that it is running
And it answers that it is ready to take work
```

#### Scenario: Not ready while the database is away

```gherkin
Given the product is running
But its database cannot be reached
When a monitor checks it
Then the product answers that it is running
But it answers that it is not ready, because its database is unavailable
And the answer does not say where the database is
```

#### Scenario: A monitor's quick check is answered

```gherkin
Given the product is running with its database
When a monitor makes a quick check that asks for no details
Then the monitor is told the product is running
```
