# partitions-and-versions

## Purpose
Work is addressed in business words. A partition is a business slice of a dataset, such as one shop on one day, and a version is what one read of that slice produced. These are the units an operator reads again, checks and replays.

## Requirements

### Requirement: Slice a dataset in business terms
The system SHALL slice a dataset by day or month in a named time zone, by fields, by a combination of these, or by a rule written in code.

#### Scenario: Orders are sliced by shop and day

```gherkin
Given the orders dataset is sliced by shop and by day in the shop's time zone
When order 1001 of Shop 12 dated 18 October is read
Then it belongs to the slice of Shop 12 on 18 October
```

#### Scenario: The time zone decides the day

```gherkin
Given the orders dataset is sliced by day in the shop's time zone
When an order is placed just after midnight there on 19 October
Then it belongs to the slice of 19 October
```

### Requirement: Each read makes a version
The system SHALL record what each read of a slice produced, the records added, changed and deleted, as a version that never changes afterwards.

#### Scenario: A read leaves a version behind

```gherkin
Given the orders of Shop 12 on 18 October hold order 1001
When that slice is read
Then a version of that slice lists order 1001 as added
```

#### Scenario: A later read does not change an earlier version

```gherkin
Given a version of Shop 12 on 18 October lists order 1001 as added
When order 1001 changes and the slice is read again
Then a new version lists order 1001 as changed
And the earlier version still lists it as added
```

### Requirement: Versions are kept for a set time
The system SHALL keep each version for a set time after every destination has taken it.

#### Scenario: A version within its keeping time can be read

```gherkin
Given a version of Shop 12 on 18 October was delivered everywhere yesterday
When the user opens that version
Then its records can be read
```

### Requirement: A record that moves slices is an update
The system SHALL treat a record whose slice changes as an update, leaving no stale copy behind.

#### Scenario: An order moved to another day leaves no copy

```gherkin
Given order 1001 was delivered in the slice of 18 October to a destination that replaces whole slices
When its date is changed to 19 October and the flow runs
Then the destination holds order 1001 under 19 October only
```
