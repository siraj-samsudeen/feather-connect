# authoring-flows

## Purpose
A flow is ordinary Python code that says what to read, where to deliver it and when. This is how a developer, or an AI assistant, writes one, checks it and runs it on their own machine before anyone else sees it.

## Requirements

### Requirement: A flow is code
The system SHALL take a flow written as ordinary Python code, with no other language or drawing to learn.

#### Scenario: A flow written in code is recognised

```gherkin
Given the user has written the orders flow as Python code in a project
When the user asks which flows the project holds
Then the orders flow is listed
```

### Requirement: Describe a dataset
The system SHALL let the user describe a dataset by where it comes from, what identifies a record, how it is sliced and how changes are found.

#### Scenario: The description is shown back

```gherkin
Given the orders flow reads orders from the shop database, identified by order number and sliced by shop and day
When the user asks for the description of the orders dataset
Then it shows the source, the identifying field, the slicing and how changes are found
```

### Requirement: Start from a skeleton
The system SHALL create the starting code, settings and tests of a new flow or a new connector on request.

#### Scenario: A new flow starts with a passing test

```gherkin
Given the user has an empty project
When the user asks for a new flow named orders
And the user runs the project's tests
Then the tests of the orders flow pass
```

### Requirement: Run a flow on your own machine
The system SHALL run a flow once on the user's machine against stand-in systems, and say what each destination received.

#### Scenario: A local run reports what was delivered

```gherkin
Given the orders flow and three orders in the stand-in shop database
When the user runs the orders flow locally
Then the run reports three orders delivered to the warehouse
And nothing outside the user's machine was called
```

### Requirement: Check a project without running it
The system SHALL check a project without running it, and say what is wrong and how to fix it, in a form a program can also read.

#### Scenario: A sound project passes the check

```gherkin
Given the orders flow is complete
When the user checks the project
Then the check passes
```

#### Scenario: A mistake is named with its fix

```gherkin
Given the orders flow delivers to a connection the project does not define
When the user checks the project
Then the check fails
And it names the missing connection and says how to add it
```

#### Scenario: Two flows sharing a name are refused

```gherkin
Given two flows in the project both name a destination "warehouse"
When the user checks the project
Then the check fails and names both flows
```

#### Scenario: Two flows waiting on each other are refused

```gherkin
Given the daily summary flow waits for the monthly flow, and the monthly flow waits for the daily summary
When the user checks the project
Then the check fails, naming both flows
```

#### Scenario: A warning does not fail the check

```gherkin
Given the orders flow is sound but has something worth a warning
When the user checks the project
Then the check passes
And the warning is shown
```

### Requirement: Test a flow
The system SHALL give tests a way to load source records, run a flow, and check what each destination received.

#### Scenario: A test checks what a destination received

```gherkin
Given a test that loads order 1001 into the stand-in shop database
When the test runs the orders flow
Then the test can see order 1001 at the warehouse
```

### Requirement: Layered settings
The system SHALL take each setting from the environment if it sets one, else from the project, else from the built-in default, and show which of these set it.

#### Scenario: The environment's value wins

```gherkin
Given the project sets the orders flow to run every hour
And the test environment sets it to run every five minutes
When the user looks at the orders flow's settings in the test environment
Then the schedule shown is every five minutes
And it is marked as set by the environment
```
