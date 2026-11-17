# webhooks

## Purpose
Other systems can push events to the product the moment something happens. Each event is checked to be genuine, kept at once, and delivered without waiting for a schedule.

## Requirements

### Requirement: Receive an event
The system SHALL accept an event sent to a flow's address, keep it at once, and answer the sender straight away, whatever its destinations are doing.

#### Scenario: An event is accepted while its destination is down

```gherkin
Given the orders flow listens for order events and the accounts service is down
When the shop sends order 1001
Then the shop is told at once that it was received
And order 1001 is delivered when the accounts service is back
```

### Requirement: Only genuine events
The system SHALL refuse an event whose signature does not prove it came from the expected sender.

#### Scenario: A forged event is refused

```gherkin
Given the orders flow accepts events signed by the shop
When an event arrives with a wrong signature
Then it is refused
And nothing is delivered
```

### Requirement: An old event cannot be sent again
The system SHALL refuse a genuine event that is sent again long after it was made.

#### Scenario: A copied event is refused later

```gherkin
Given a genuine event for order 1001 was received yesterday
When the same event is sent again today
Then it is refused
```

### Requirement: The same event twice counts once
The system SHALL deliver an event once when its sender sends it twice.

#### Scenario: A resent event is delivered once

```gherkin
Given the shop sends the event for order 1001
When the shop sends that same event again a moment later
Then order 1001 is delivered once
```

### Requirement: Limits on what a sender can send
The system SHALL refuse an event that is too large, and slow a sender that sends too many.

#### Scenario: An oversized event is refused

```gherkin
Given events may be at most a set size
When an event larger than that arrives
Then it is refused, saying it is too large
```

### Requirement: A burst loses nothing
The system SHALL lose no event when events arrive at ten times the usual rate, and return to its usual delay within five minutes.

#### Scenario: Every event of a burst is delivered

```gherkin
Given events usually arrive at a steady rate
When ten times as many arrive for a minute
Then every one of them is delivered once
```
