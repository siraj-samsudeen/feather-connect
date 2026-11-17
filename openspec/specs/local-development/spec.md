# local-development

## Purpose
Trying the product, or working on a flow, should take minutes. One command brings up everything on a developer's own machine with a working example to look at.

## Requirements

### Requirement: One command starts everything
The system SHALL start everything needed on the user's machine with one command, with an example flow running, and say where the dashboard is and how to sign in.

#### Scenario: The example flow is on screen in minutes

```gherkin
Given the user has installed the product on a clean machine
When the user runs the start command
Then within five minutes the dashboard shows the example flow delivering records
```

### Requirement: A change is picked up
The system SHALL pick up a change to a flow's code without the user starting again.

#### Scenario: An edited flow runs with the edit

```gherkin
Given the local setup is running with the user's orders flow
When the user changes the flow's code and saves it
Then the next run of the orders flow uses the changed code
```

### Requirement: Clear when something is missing
The system SHALL say plainly what is missing when the local setup cannot start.

#### Scenario: A missing requirement is named

```gherkin
Given the user's machine lacks something the local setup needs
When the user runs the start command
Then it stops, naming what is missing and how to get it
```
