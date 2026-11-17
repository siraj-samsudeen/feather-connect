# flow-packages

## Purpose
Flows reach an environment as a package: a versioned bundle built in the team's own repository. A package is installed, its flows are switched on one by one, and versions are changed or taken back, all without stopping anything else.

## Requirements

### Requirement: Build and publish a package
The system SHALL build a project's flows into a versioned package and publish it to the server's own registry.

#### Scenario: A published version can be found

```gherkin
Given the user has built version 1.4 of the orders package
When the user publishes it
Then version 1.4 of the orders package is listed in the registry
```

#### Scenario: A published version is never replaced

```gherkin
Given version 1.4 of the orders package is published
When the user publishes different content as version 1.4
Then the registry refuses it
```

### Requirement: Publishing rights only
The system SHALL allow a token that can publish new versions and do nothing else.

#### Scenario: A publishing token cannot install

```gherkin
Given a token limited to publishing
When it is used to install the orders package
Then the request is refused
```

### Requirement: Install a package
The system SHALL check a package when it is installed, keep it, and leave its flows switched off.

#### Scenario: Installed flows start switched off

```gherkin
Given version 1.4 of the orders package is published
When the user installs it in the test environment
Then the orders flow is listed there as switched off
```

#### Scenario: A package that fails its checks is not installed

```gherkin
Given a published package whose flows cannot be loaded
When the user installs it
Then the install fails and says which check failed
```

### Requirement: Install from a file
The system SHALL install a package from a file, behind the same checks, where the registry cannot be reached.

#### Scenario: A package file is installed

```gherkin
Given the user has version 1.4 of the orders package as a file
When the user installs it from the file
Then the orders flow is listed as switched off
```

### Requirement: Runs what was tested
The system SHALL run a package with exactly the versions of the libraries it was built with, apart from every other package.

#### Scenario: Two packages need different versions of a library

```gherkin
Given the orders package and the prices package each need a different version of the same library
When both are switched on
Then each runs with its own version
```

### Requirement: Switch a flow on and off
The system SHALL switch each flow on and off per environment, letting runs in progress finish.

#### Scenario: A flow switched on starts running

```gherkin
Given the orders flow is installed and switched off
When the user switches it on
Then its next scheduled run takes place
```

#### Scenario: Switching off lets a run finish

```gherkin
Given the orders flow is in the middle of a run
When the user switches it off
Then that run finishes
And no further run starts
```

### Requirement: Only a checked version can be switched on
The system SHALL refuse to switch on a version that has not passed its loading check.

#### Scenario: A version still being prepared is refused

```gherkin
Given version 1.5 of the orders package is installed but still being prepared
When the user switches on its orders flow
Then the request is refused with the reason
```

### Requirement: Change version and go back
The system SHALL replace the running version of a flow with another, forwards or backwards, with no run lost or run twice.

#### Scenario: Going back to the earlier version

```gherkin
Given the orders flow runs version 1.5 and version 1.4 is still installed
When the user switches version 1.4 on
Then the orders flow runs version 1.4
And every order is delivered once
```

### Requirement: Nothing else stops
The system SHALL install, change, take back and switch off a package without restarting anything and without disturbing other packages.

#### Scenario: Another package keeps running

```gherkin
Given the prices flow of another package is running
When the user changes the orders flow from version 1.4 to 1.5
Then the prices flow's runs carry on without a gap
```

### Requirement: Names carry the package
The system SHALL show every flow, dataset and destination under its package's name, so two packages cannot clash.

#### Scenario: Two packages use the same flow name

```gherkin
Given the orders package and the returns package each hold a flow named sync
When both are installed
Then both flows are listed, each under its package's name
```

### Requirement: Promote what was tested
The system SHALL promote a package from one environment to the next only as the identical content, and show which version of the code each flow runs.

#### Scenario: The promoted package is the tested one

```gherkin
Given version 1.4 of the orders package runs in the test environment
When the user promotes it to production
Then production holds the identical package
And the orders flow there shows version 1.4
```

### Requirement: Signed packages
The system SHALL let an environment refuse packages that are not signed with its key.

#### Scenario: An unsigned package is refused

```gherkin
Given production accepts only signed packages
When the user installs an unsigned orders package there
Then the install is refused
```

### Requirement: Change a schedule without a new version
The system SHALL let the user change a flow's schedule, or switch the flow off, in one environment without publishing a new version.

#### Scenario: A schedule changed in one environment

```gherkin
Given the orders flow runs every hour as its package says
When the user sets it to run every ten minutes in the test environment
Then it runs every ten minutes there
And the package's own schedule is shown beside the change
```

### Requirement: Uninstall a version
The system SHALL uninstall a version only when none of its flows is switched on, and keep its history.

#### Scenario: A version in use cannot be uninstalled

```gherkin
Given the orders flow of version 1.4 is switched on
When the user uninstalls version 1.4
Then the request is refused
```

#### Scenario: History stays after uninstalling

```gherkin
Given version 1.4 of the orders package is switched off and has past runs
When the user uninstalls it
Then its past runs can still be looked at
```

### Requirement: A team's own package index
The system SHALL let an administrator add a team's own package index beside the built-in registry, test that it can be reached, and remove it.

#### Scenario: A team's index is added and used

```gherkin
Given the team keeps its packages in its own index
When an administrator adds that index and tests it
Then the test passes
And the team's packages can be installed from it
```

### Requirement: Withdraw a version
The system SHALL let a published version be withdrawn, so it is no longer offered for install, without disturbing an environment that runs it.

#### Scenario: A withdrawn version keeps running where it is

```gherkin
Given version 1.4 of the orders package is published and switched on in the test environment
When the user withdraws version 1.4
Then version 1.4 is no longer offered for install
And the test environment keeps running it
```
