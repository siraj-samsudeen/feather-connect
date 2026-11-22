# Logs and health

## Purpose

The host the product runs on (the service that starts it and restarts it), or an uptime monitor
(a service that checks a site every minute or so), can tell whether the product is running and
whether it is ready to take work. Ready means the product can use its database, and the database
has every upgrade this version needs.

## Requirements

### Requirement: Health an outside monitor can check
The system SHALL answer, at fixed addresses open to any monitor, whether it is running and whether it is ready to take work, without saying where its database is or what went wrong with it.

#### Scenario: Running and ready

```gherkin
Given the product is running with its database
When a monitor checks it
Then the product answers that it is running
And it answers that it is ready to take work
```

#### Scenario: Not ready while the database is away

```gherkin
Given the product is running
But its database cannot be reached
When a monitor checks it
Then the product answers that it is running
But it answers that it is not ready, because its database is unavailable
And the answer does not say where the database is
```

#### Scenario: A monitor's quick check is answered

```gherkin
Given the product is running with its database
When a monitor makes a quick check that asks for no details
Then the monitor is told the product is running
```

### Requirement: Not ready while the database is behind
The system SHALL answer that it is not ready while its database waits for an upgrade (a change to the database this version needs), and its log SHALL say how to upgrade it.

#### Scenario: Not ready on a database that waits for an upgrade

```gherkin
Given the product is running on a new, empty database
When a monitor checks it
Then the product answers that it is running
But it answers that it is not ready, because its database is unavailable
And its log says the database is behind, and how to upgrade it
```

#### Scenario: Ready by itself once the database is upgraded

```gherkin
Given the product is running on a new, empty database
When the operator upgrades the database
Then the product answers that it is ready to take work, without being restarted
```

### Requirement: Not ready with a changed upgrade
The system SHALL answer that it is not ready when an upgrade already applied to its database has since been changed, and its log SHALL name that upgrade.

#### Scenario: Not ready when an applied upgrade was edited

```gherkin
Given the product is running on a database that has been upgraded
But one of its applied upgrades has been edited since it ran
When a monitor checks it
Then it answers that it is not ready, because its database is unavailable
And its log names the upgrade that changed, and says to restore it
```

### Requirement: Ready on a database a newer version upgraded
The system SHALL stay ready when its database holds upgrades from a newer version of the product, as after going back to an older version.

#### Scenario: Still ready after going back to an older version

```gherkin
Given the product is running on a database that has been upgraded
And the database has one more upgrade, from a newer version
When a monitor checks it
Then the product answers that it is ready to take work
```
