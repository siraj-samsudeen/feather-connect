# shape-changes

## Purpose
Sources change: a field appears, disappears or changes its kind. Harmless changes pass on their own; changes that could damage a destination wait for a person.

## Requirements

### Requirement: Added fields pass, risky changes wait
The system SHALL deliver a version whose records gained a field, and hold a version whose records lost a field or changed a field's kind until a person decides.

#### Scenario: A new field is delivered

```gherkin
Given orders have been delivered to the warehouse
When orders start carrying a new field for a gift note
Then the next version is delivered with the gift note
```

#### Scenario: A dropped field waits for a person

```gherkin
Given orders have been delivered to the warehouse
When orders stop carrying the customer field
Then the next version waits for a decision, saying a field was dropped
And earlier versions at the warehouse are untouched
```

### Requirement: The rule can be stricter or looser
The system SHALL let a dataset or a destination hold on any change of shape, or on none.

#### Scenario: A strict destination holds on an added field

```gherkin
Given the accounts service route holds on any change of shape
When orders start carrying a new field
Then the next version to the accounts service waits for a decision
And the same version is delivered to the warehouse
```
