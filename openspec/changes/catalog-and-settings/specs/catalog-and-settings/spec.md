# Catalog and Settings

## Purpose

Flows, datasets and routes are written in Python and shipped in a package. A flow is a piece of
work that runs; a dataset is the data one source gives; a route takes a dataset to one
destination. When a version of a package is installed, the product records what it declares: the
catalog. Each flow, dataset and route keeps its full name, such as shop-flows.orders, across
the package's versions, so its history and its settings follow it.

Code decides the logic: where data comes from, its key, how it is split, how it is changed and
written. Operators own the rest: a setting is something an operator changes per environment (a
deployment such as production) without a new package, such as a schedule, a look-back (how far
back each read starts again), the number of tries, or a pause with an end. For every setting the operator sees the
value in force and who set it: the operator, the code, or the product's default. Covers R1.9,
R2.6, R2.9, R2.12, R9.2 (for settings), R10.4 (for settings).

## ADDED Requirements

### Requirement: Record what a package version declares
The system SHALL record each flow, dataset and route a package version declares, each under its full name, so a later version's changes never alter what an earlier version declared.

#### Scenario: The catalog lists what the package declares

```gherkin
Given the package version "shop-flows 1.0" declares the flow "shop-flows.daily", the dataset "shop-flows.orders" and the route "shop-flows.orders-to-crm"
When the developer records "shop-flows 1.0"
Then the catalog lists the flow "shop-flows.daily", the dataset "shop-flows.orders" and the route "shop-flows.orders-to-crm", each from "shop-flows 1.0"
```

### Requirement: A recorded package version never changes
The system SHALL refuse to record a package version again with different definitions, and say to give the changed code a new version.

#### Scenario: Changed definitions under the same version are refused

```gherkin
Given "shop-flows 1.0" has been recorded
When the developer records "shop-flows 1.0" again, with the dataset "shop-flows.orders" declared differently
Then the recording is refused, saying a recorded version never changes and to give the code a new version
And the catalog still has the first definition of "shop-flows 1.0"
```

### Requirement: The operator's value is in force, else the code's
The system SHALL use the operator's value of a setting when there is one, else the code's, else the product's default, and show each value in force with who set it.

#### Scenario: The operator's look-back is in force

```gherkin
Given "shop-flows 1.0" has been recorded, its code giving the dataset "shop-flows.orders" a look-back of "1d" and a batch size of "5000"
When the operator sets the look-back of "shop-flows.orders" to "3d"
Then the settings of "shop-flows.orders" show the look-back "3d", set by the operator
And they show the batch size "5000", set by the code
```

#### Scenario: The product's default applies when neither gives a value

```gherkin
Given "shop-flows 1.0" has been recorded, its code giving the dataset "shop-flows.orders" no number of tries
When the operator looks at the settings of "shop-flows.orders"
Then they show the number of tries "6", set by the product's default
```

#### Scenario: Clearing the operator's value brings back the code's

```gherkin
Given "shop-flows 1.0" has been recorded, its code giving the dataset "shop-flows.orders" a look-back of "1d"
And the operator has set the look-back of "shop-flows.orders" to "3d"
When the operator clears the look-back of "shop-flows.orders"
Then the settings of "shop-flows.orders" show the look-back "1d", set by the code
```

### Requirement: An operator's value outlives an upgrade
The system SHALL keep an operator's value when a later package version of the same name is recorded, even when the new code gives that setting another value.

#### Scenario: The look-back stays the operator's after an upgrade

```gherkin
Given "shop-flows 1.0" has been recorded, its code giving the dataset "shop-flows.orders" a look-back of "1d"
And the operator has set the look-back of "shop-flows.orders" to "3d"
When the developer records "shop-flows 1.1", its code giving "shop-flows.orders" a look-back of "2d"
Then the settings of "shop-flows.orders" show the look-back "3d", set by the operator
```

### Requirement: A rename is explicit
The system SHALL carry a name's history and settings over to a new name only when the code says the new name replaces the old one; any other new name starts afresh.

#### Scenario: A renamed dataset keeps the operator's settings

```gherkin
Given "shop-flows 1.0" has been recorded, and the operator has set the look-back of "shop-flows.orders" to "3d"
When the developer records "shop-flows 2.0", which renames "shop-flows.orders" to "shop-flows.sales-orders"
Then the settings of "shop-flows.sales-orders" show the look-back "3d", set by the operator
And the catalog no longer lists "shop-flows.orders"
```

#### Scenario: A new name without a rename starts afresh

```gherkin
Given "shop-flows 1.0" has been recorded, and the operator has set the look-back of "shop-flows.orders" to "3d"
When the developer records "shop-flows 2.0", which declares "shop-flows.sales-orders" without saying it replaces "shop-flows.orders"
Then the settings of "shop-flows.sales-orders" show no value set by the operator
```

### Requirement: An operator's value the code no longer uses is flagged, never dropped
The system SHALL keep an operator's value for a name a newer package version no longer declares, and flag it, both when that version is recorded and in the list of every value operators have set, until the operator clears it.

#### Scenario: The operator is told about a look-back the new code no longer uses

```gherkin
Given "shop-flows 1.0" has been recorded, and the operator has set the look-back of "shop-flows.orders" to "3d"
When the developer records "shop-flows 2.0", which no longer declares "shop-flows.orders"
Then the recording warns that the operator's look-back of "shop-flows.orders" is for a name the code no longer has
And the list of every value operators have set shows the look-back "3d" of "shop-flows.orders", flagged as no longer in the code
```

### Requirement: Only an operator's settings can be changed, to a valid value
The system SHALL refuse a change to something the code decides, or to a setting the kind does not have, and refuse a value of the wrong form, saying what is expected.

#### Scenario: The dataset's key is the code's to decide

```gherkin
Given "shop-flows 1.0" has been recorded
When the operator sets the key of "shop-flows.orders" to "order_number"
Then the change is refused, saying the key is decided by the code, and naming the settings a dataset has
```

#### Scenario: A look-back in words is refused

```gherkin
Given "shop-flows 1.0" has been recorded, its code giving the dataset "shop-flows.orders" a look-back of "1d"
When the operator sets the look-back of "shop-flows.orders" to "three days"
Then the change is refused, saying a look-back is a length of time such as "3d" or "12h"
And the settings of "shop-flows.orders" still show the look-back "1d", set by the code
```

### Requirement: Every change says who made it and why
The system SHALL record every change to a setting, refused ones included, with who made it, when and the reason given; in a protected environment it SHALL refuse a change that gives no reason.

#### Scenario: The audit log has the change with its reason

```gherkin
Given "shop-flows 1.0" has been recorded
When the operator sets the look-back of "shop-flows.orders" to "3d", giving the reason "the source posts late corrections"
Then the audit log records the change of the look-back of "shop-flows.orders" to "3d", by the operator, with the reason "the source posts late corrections"
```

#### Scenario: A change without a reason is refused in a protected environment

```gherkin
Given a protected environment where "shop-flows 1.0" has been recorded
When the operator sets the look-back of "shop-flows.orders" to "3d", giving no reason
Then the change is refused, saying a protected environment needs a reason for every change
And the audit log records the refusal
And the settings of "shop-flows.orders" show no value set by the operator
```
