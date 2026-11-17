# flow-templates

## Purpose
A template is a ready-made flow for a common job. A developer copies one into a project and edits it freely; from then on it is their own code.

## Requirements

### Requirement: Start a flow from a template
The system SHALL copy a template into the user's project as ordinary code the user can edit, for at least these jobs: a table to a warehouse, a web service to a warehouse, files to a database, a webhook to a web service, and one source to several destinations.

#### Scenario: A copied template runs as it is

```gherkin
Given the user has an empty project
When the user starts a flow from the table-to-warehouse template
And the user runs it locally
Then the run delivers the template's sample records to the stand-in warehouse
```

### Requirement: A template is complete
The system SHALL ship every template with its code, its settings for each environment, sample data, tests and a description.

#### Scenario: A copied template's tests pass

```gherkin
Given the user has started a flow from the table-to-warehouse template
When the user runs the project's tests
Then the template's tests pass
```
