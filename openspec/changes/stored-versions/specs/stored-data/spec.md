# Stored data

## Purpose
A flow reads records from a source into a dataset, such as a shop's orders. A dataset is split
into slices, such as one shop's orders of one day, and each slice is named in business words
("Shop 12 · 18 Oct 2026"). Each read of a slice is kept as a version of it, which counts only
once the whole read is in. A version keeps only the records that changed since the hub last saw
them, so nothing unchanged is ever sent on again. Until the dashboard's data pages and the
connector kit exist, a developer reads records into a dataset, and follows them, from the
command line.

## ADDED Requirements

### Requirement: Each read is kept as a version of its slice
The system SHALL keep each read of a slice as the slice's next version, whether it was a complete read or changes only, and say how many records were read and how many of them were added, changed or unchanged; records found deleted are counted beside them.

#### Scenario: The first read of a slice adds every record

```gherkin
Given a dataset of orders, split by shop and by day
When the user reads orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
Then the slice "Shop 12 · 18 Oct 2026" has 1 version
And version 1 counts 3 records read: 3 added, 0 changed, 0 deleted and 0 unchanged
```

### Requirement: Unchanged records are left out
The system SHALL keep in a version only the records that changed since the hub last saw them.

#### Scenario: Only the changed order is kept

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
When the user reads the same three orders again, with order 1002's amount changed
Then version 2 counts 3 records read: 0 added, 1 changed, 0 deleted and 2 unchanged
And version 2 holds order 1002 only
```

#### Scenario: A read that changes nothing adds no version

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
When the user reads the same three orders again, unchanged
Then the user is told nothing changed
And the slice "Shop 12 · 18 Oct 2026" has 1 version
```

### Requirement: The last copy of a record counts
The system SHALL keep the last copy when one read holds a record more than once.

#### Scenario: The later copy of an order is the one kept

```gherkin
Given a dataset of orders, split by shop and by day
When the user reads order 1001 of shop 12, ordered on 18 Oct 2026, twice in one read, first with an amount of 10.00, then of 12.00
Then following order 1001 shows an amount of 12.00
```

### Requirement: A complete read finds the records deleted at the source
The system SHALL mark as deleted the records that a complete read of a slice, one that returns every record of the slice, no longer returns.

#### Scenario: An order missing from a complete read is deleted

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
When the user reads that slice in full, and it returns orders 1001 and 1002 only
Then version 2 is a complete read
And version 2 counts 2 records read: 0 added, 0 changed, 1 deleted and 2 unchanged
And following order 1003 shows it was removed at the source
```

### Requirement: An empty complete read is refused
The system SHALL refuse a complete read that returns nothing, so an empty answer cannot empty a slice, unless the dataset allows an empty slice.

#### Scenario: A complete read that returns nothing is refused

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
When the user reads that slice in full, and it returns no orders
Then the read is refused, and the user is told the slice would be emptied
And the slice "Shop 12 · 18 Oct 2026" has 1 version
```

#### Scenario: A dataset that allows an empty slice is emptied

```gherkin
Given a dataset of orders, split by shop and by day, that allows an empty slice
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
When the user reads that slice in full, and it returns no orders
Then version 2 counts 0 records read: 0 added, 0 changed, 3 deleted and 0 unchanged
```

### Requirement: A record that moves to another slice is an update
The system SHALL keep a record that is read in another slice than before as a change in the new slice only, never as a delete and a new record.

#### Scenario: An order whose date was edited moves to the new day

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
When the user reads order 1002 again, now ordered on 19 Oct 2026
Then the slice "Shop 12 · 19 Oct 2026" has 1 version
And its version 1 counts 1 record read: 0 added, 1 changed, 0 deleted and 0 unchanged
And following order 1002 shows it in the slice "Shop 12 · 19 Oct 2026"
And the slice "Shop 12 · 18 Oct 2026" has 1 version
```

### Requirement: Follow a record by its key
The system SHALL show one record by its key: its content, the slice it is in, the version that last changed it, and whether it is still at the source.

#### Scenario: Following an order shows what last changed it

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026
And the user has read order 1002 again, with its amount changed to 12.00
When the user follows order 1002
Then it shows an amount of 12.00, in the slice "Shop 12 · 18 Oct 2026"
And it was last changed by version 2
```

### Requirement: See a record as it was at an earlier commit
The system SHALL give every sealed version of a dataset the dataset's next commit number, and show a record as it was at any commit number still kept.

#### Scenario: An order as it was at commit 1

```gherkin
Given a dataset of orders, split by shop and by day
And the user has read orders 1001, 1002 and 1003 of shop 12, ordered on 18 Oct 2026, each for 10.00
And the user has read order 1002 again, with its amount changed to 12.00
When the user follows order 1002 as of commit 1
Then it shows an amount of 10.00
And version 1 is commit 1, and version 2 is commit 2
```
