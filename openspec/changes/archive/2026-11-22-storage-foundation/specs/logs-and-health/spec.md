# Logs and health

## ADDED Requirements

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
