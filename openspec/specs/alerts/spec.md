# alerts

## Purpose
People should hear about a problem without watching a screen. Rules say what counts as a problem, and an alert goes to the place a team already reads.

## Requirements

### Requirement: Rules for what needs attention
The system SHALL raise an alert when a run fails, a delivery stays failed, a budget is nearly used up, work has waited too long for a decision, scheduled starts keep being skipped, a dataset is out of date, a dataset has gone quiet, or no worker is running.

#### Scenario: A failed delivery raises an alert

```gherkin
Given the rule for failed deliveries is on
When the delivery of order 1001 has stayed failed past the rule's time
Then an alert is raised naming that delivery
```

#### Scenario: No worker running raises an alert

```gherkin
Given the rule for workers is on
When the last worker stops
Then an alert is raised saying no worker is running
```

#### Scenario: The alert clears when a worker is back

```gherkin
Given an alert says no worker is running
When a worker starts again
Then that alert clears
```

#### Scenario Outline: Each rule raises its alert

```gherkin
Given the rule for <problem> is on
When there is <problem>
Then an alert is raised about <problem>

Examples:
  | problem |
  | a failed run |
  | a budget nearly used up |
  | a hold waiting too long |
  | scheduled starts skipped again and again |
  | a dataset out of date |
  | a dataset gone quiet |
```

### Requirement: Rules per environment
The system SHALL let each environment switch rules on and off and set their limits.

#### Scenario: A rule is off in test and on in production

```gherkin
Given the rule for failed runs is on in production and off in the test environment
When a run fails in each
Then an alert is raised in production only
```

### Requirement: Send alerts where the team reads
The system SHALL send an alert to the channels chosen for it: a web address, a team chat, or email.

#### Scenario Outline: An alert reaches each kind of channel

```gherkin
Given alerts go to <channel>
When an alert is raised
Then a message about it arrives at <channel>

Examples:
  | channel |
  | a web address |
  | the team chat |
  | an email address |
```

### Requirement: Test a channel
The system SHALL send a test alert to a channel on request.

#### Scenario: A test alert arrives

```gherkin
Given a team chat channel is set up
When the user sends it a test alert
Then a test message arrives in the team chat
```

### Requirement: One alert per problem
The system SHALL not raise a second alert for a problem it has already alerted about and that is still going on.

#### Scenario: A lasting failure alerts once

```gherkin
Given an alert was raised for a failed delivery
When the delivery is still failed an hour later
Then no second alert is raised for it
```

### Requirement: Acknowledge and snooze
The system SHALL let the user acknowledge an alert, or quiet it for a set time.

#### Scenario: A snoozed alert stays quiet

```gherkin
Given an alert is raised for a budget nearly used up
When the user snoozes it for an hour
Then it sends no further message during that hour
```
