# ai-assistance

## Purpose
AI assistants write flows and AI agents investigate problems. The product gives them what they need to do that well, and no more rights than a person in the same role would have.

## Requirements

### Requirement: A project an assistant can work in
The system SHALL put, in every new project, written guidance for AI assistants on how flows are written and tested here.

#### Scenario: A new project carries the guidance

```gherkin
Given the user creates a new project
When an AI assistant opens it
Then it finds the guidance on writing and testing flows
```

### Requirement: Ask what a connector can do
The system SHALL describe any connector on request, in a form a program can read: its settings and what it can do.

#### Scenario: An agent asks about a connector

```gherkin
Given an agent wants to read from a web service
When it asks for the description of the web service connector
Then it receives the connector's settings and abilities in a form it can read
```

### Requirement: An agent that can look and not touch
The system SHALL give an agent holding a read-only token tools to look at flows, runs, failures, records and budgets, and no tool that changes anything.

#### Scenario: An agent finds out why a delivery failed

```gherkin
Given the delivery of order 1001 failed with an error
When an agent with a read-only token investigates it
Then the agent can read the error and the steps that led to it
```

#### Scenario: The agent cannot change anything

```gherkin
Given an agent with a read-only token
When the agent tries to retry the delivery
Then the request is refused
```

### Requirement: An agent sees what a person would
The system SHALL give an agent data masked as it is for a person in the same role, marked as content that is not to be trusted as instructions, and never a secret.

#### Scenario: Personal data is masked for an agent

```gherkin
Given the orders dataset marks the customer's email as personal
When an agent with a read-only token reads order 1001
Then the email is masked
```

### Requirement: A ready-made way to investigate
The system SHALL provide a written procedure an agent can follow to investigate a failed delivery.

#### Scenario: The procedure leads to the cause

```gherkin
Given the delivery of order 1001 failed because the accounts service refused the sign-in
When an agent follows the procedure for a failed delivery
Then it reports that the sign-in was refused
```

### Requirement: Measure how well AI writes flows
The system SHALL keep a fixed set of flow-writing tasks, each with tests the writer does not see, to measure how many an AI assistant gets right without help.

#### Scenario: A correct answer passes its hidden tests

```gherkin
Given a task from the set and a correct flow written for it
When the hidden tests of that task are run
Then they pass
```

### Requirement: Local tools that change nothing
The system SHALL give an agent tools on the developer's machine that check a project and describe connectors, without a server and without changing anything.

#### Scenario: An agent checks a project locally

```gherkin
Given an agent has written a flow on the developer's machine
When it checks the project with the local tools
Then it receives the result of the check in a form it can read
And nothing outside the developer's machine was called
```
