# recovery-actions

## Purpose
Seeing a problem is half the job; the other half is fixing it from the same place. An operator can run, read again, retry, skip and replay, always seeing first what an action will touch.

## Requirements

### Requirement: Run, read again, cancel
The system SHALL let the user run a flow now, read chosen slices again, and cancel a run.

#### Scenario: A slice is read again

```gherkin
Given the source has corrected the orders of Shop 12 on 18 October
When the user reads that slice again
Then the corrected orders are delivered
```

#### Scenario: A cancelled run stops

```gherkin
Given a run of the orders flow is in progress
When the user cancels it
Then the run stops and is marked as cancelled
```

### Requirement: Retry or skip a failed delivery
The system SHALL let the user retry a failed delivery, or skip it so that later ones can go on.

#### Scenario: A retried delivery succeeds

```gherkin
Given the delivery of order 1001 to the accounts service failed while the service was down
And the service is back
When the user retries that delivery
Then order 1001 is delivered
```

#### Scenario: Skipping lets the next version through

```gherkin
Given a failed delivery holds back a later version of the same slice
When the user skips the failed delivery with a reason
Then the later version is delivered
And the skipped one shows who skipped it and why
```

### Requirement: See the effect before acting on many
The system SHALL show what an action on many items will touch, and what it is expected to cost against call budgets, and act only when the user confirms shortly after.

#### Scenario: A mass retry is previewed

```gherkin
Given twenty deliveries to the accounts service have failed
When the user asks to retry them all
Then a preview lists the twenty deliveries and the calls expected
And nothing is retried until the user confirms
```

#### Scenario: A stale confirmation is refused

```gherkin
Given the user was shown a preview an hour ago
When the user confirms it now
Then the action is refused and a new preview is offered
```

#### Scenario: A confirmation covers only what was previewed

```gherkin
Given the user was shown a preview of retrying twenty deliveries
And a twenty-first delivery has failed since
When the user confirms
Then the twenty are retried and the twenty-first is not
```

### Requirement: An action points to its record
The system SHALL show, with the result of every action, where it was written in the audit log.

#### Scenario: A retry leads to its audit entry

```gherkin
Given the user has retried a delivery
When the result is shown
Then the user can go from it to the entry recording that retry
```

### Requirement: Check a slice against its source
The system SHALL read a slice again on request and say whether it differs from the last read, changing nothing.

#### Scenario: A check finds a change and delivers nothing

```gherkin
Given the orders of Shop 12 on 18 October were read yesterday
And one of them has since changed at the source
When the user checks that slice
Then it reports one changed order
And nothing is delivered
```

### Requirement: Send again or dismiss a record set aside
The system SHALL let the user send a record that was set aside again once its cause is fixed, or dismiss it with a reason.

#### Scenario: A fixed record is sent again

```gherkin
Given order 1002 was set aside because the accounts service turned it down
And the cause has been fixed at the accounts service
When the user sends order 1002 again
Then order 1002 is delivered
```

#### Scenario: A record is dismissed with a reason

```gherkin
Given order 1002 was set aside and is only a test order
When the user dismisses it with a reason
Then it is no longer listed as set aside
And the dismissal and its reason are in the audit log
```

### Requirement: Act on several flows or runs at once
The system SHALL let the user run, pause or resume several flows, or cancel several runs, at once, up to a hundred.

#### Scenario: Three flows are paused together

```gherkin
Given the orders, prices and stock flows are running
When the user pauses the three together
Then all three are paused
```

#### Scenario: Too many at once are refused

```gherkin
Given a selection of 150 flows
When the user runs them together
Then the request is refused, saying at most a hundred can be acted on at once
```
