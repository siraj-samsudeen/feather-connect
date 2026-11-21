# Database upgrades

## Purpose

A new version of the product may need changes to its database: an upgrade. The operator (the
person who runs the product on a host) applies the waiting upgrades with one command before the
new version starts, and can see what has been applied and what still waits. Upgrades only ever
add, so the version already running keeps working while they are applied.

## ADDED Requirements

### Requirement: See what has been applied and what waits
The system SHALL list the upgrades already applied, with when each ran, and those still waiting.

#### Scenario: A new database shows every upgrade waiting

```gherkin
Given a new, empty database
When the operator asks for the database's status
Then every upgrade of this version is listed as waiting
```

#### Scenario: An upgraded database shows when each upgrade ran

```gherkin
Given a database that has been upgraded
When the operator asks for the database's status
Then every upgrade of this version is listed as applied, with when it ran
And none is listed as waiting
```

### Requirement: Upgrade the database with one command
The system SHALL apply, with one command, every upgrade the database is waiting for, and say how many it applied.

#### Scenario: The operator is told how many upgrades were applied

```gherkin
Given a new, empty database
When the operator upgrades the database
Then the operator is told how many upgrades were applied
And the database is up to date
```

#### Scenario: An upgraded database is said to be up to date already

```gherkin
Given a database that has been upgraded
When the operator upgrades the database
Then the operator is told the database was already up to date
```

### Requirement: One upgrade at a time
The system SHALL apply each upgrade once when the upgrade command is started more than once at the same time, for example by two copies of the product being deployed together.

#### Scenario: Two upgrades at once both end well

```gherkin
Given a new, empty database
When the operator starts two upgrades of the database at the same time
Then both finish without an error
And the database is up to date
```

### Requirement: A changed upgrade is refused
The system SHALL refuse to upgrade a database in which an upgrade it already applied has since been changed, naming that upgrade and saying to restore it.

#### Scenario: The operator is told which upgrade was edited

```gherkin
Given a database that has been upgraded
But one of its applied upgrades has been edited since it ran
When the operator upgrades the database
Then the upgrade is refused
And the operator is told which upgrade changed, and to restore it
```
