# tenants

## Purpose
One environment may one day serve several tenants: separate groups, each with its own data and settings. Until then there is one, and nobody should have to think about it; but nothing may be built in a way that would let tenants mix later.

## Requirements

### Requirement: One tenant, never in the way
The system SHALL run with a single tenant without ever showing it or asking for it.

#### Scenario: The user never meets the word

```gherkin
Given a newly installed environment
When the user sets up a flow and runs it
Then the user is never asked to choose or name a tenant
```

### Requirement: Everything belongs to a tenant
The system SHALL keep every item it stores as belonging to one tenant, and never give an item of one tenant in answer to a request for another.

#### Scenario: A request for another tenant finds nothing

```gherkin
Given order 1001 belongs to the environment's own tenant
When a request asks for order 1001 on behalf of a different tenant
Then nothing is returned
```
