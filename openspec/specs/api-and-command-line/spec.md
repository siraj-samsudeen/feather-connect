# api-and-command-line

## Purpose
Everything the dashboard does can also be done by a script or from a terminal, under the same rights and leaving the same trace. This is what lets pipelines, scripts and AI agents use the product safely.

## Requirements

### Requirement: The same actions everywhere
The system SHALL offer every action of the dashboard through its programming interface and its command line, with the same rights and the same record of who did what.

#### Scenario: A retry from the command line is recorded like any other

```gherkin
Given the delivery of order 1001 has failed
When the user retries it from the command line
Then order 1001 is delivered
And the audit log shows the user retried it
```

#### Scenario: Rights hold outside the dashboard

```gherkin
Given a user who may only look
When that user asks to retry a delivery through the programming interface
Then the request is refused
```

### Requirement: Answers a program can read
The system SHALL let every command answer in a form a program can read.

#### Scenario: A script reads the list of failures

```gherkin
Given one delivery has failed
When a script asks for the failures in the form for programs
Then the answer lists that delivery in a form the script can read
```

### Requirement: A repeated request takes effect once
The system SHALL carry out a request once when it is sent again with the same key.

#### Scenario: A resent request does not run twice

```gherkin
Given a script asked to run the orders flow and did not get the answer
When the script sends the same request again with the same key
Then the orders flow has run once
```

### Requirement: The interface is described
The system SHALL publish a description of its programming interface that tools can read.

#### Scenario: The description lists the retry action

```gherkin
Given the product is running
When a tool reads the description of the programming interface
Then it finds the action that retries a delivery, with what it needs and what it answers
```
