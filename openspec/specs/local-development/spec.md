# Local development

## Purpose

Starting the product, on a developer's machine or a host, should not need a programmer to read
what went wrong.

## Requirements

### Requirement: Clear errors, not stack traces
When a setting is wrong or the database cannot be used, the system SHALL say what is wrong and what to do, without a stack trace (the program's own listing of where it failed).

#### Scenario: A missing database address is explained

```gherkin
Given no database address has been set
When the user starts the server
Then the server does not start
And it says the database address is missing, and how to set it
```

#### Scenario: A port that is taken is named

```gherkin
Given another program is using the server's port (the number it listens on)
When the user starts the server
Then the server does not start
And it names the port, and says how to choose another
```
