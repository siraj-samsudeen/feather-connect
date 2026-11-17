# dashboard-basics

## Purpose
Promises that hold on every page of the dashboard, so that feature specs need not repeat them: it can be used by anyone, on any screen, by keyboard alone, and safely.

## Requirements

### Requirement: Pages that show information work without scripts
The system SHALL show every page that only presents information when scripts are switched off in the browser.

#### Scenario: The list of flows opens with scripts off

```gherkin
Given the user has switched scripts off in the browser
When the user opens the list of flows
Then the flows are listed
```

### Requirement: Usable by keyboard alone
The system SHALL let every action on every page be done with the keyboard alone.

#### Scenario: A delivery is retried without a mouse

```gherkin
Given a failed delivery is listed
When the user reaches it and retries it using only the keyboard
Then the delivery is retried
```

### Requirement: Accessible to everyone
The system SHALL meet the accessibility standard WCAG 2.1 at level AA on its main pages, in its light and its dark appearance, and never show a state by colour alone.

#### Scenario: A failure is not shown by colour alone

```gherkin
Given a failed delivery is listed
When the user looks at it without seeing colour
Then it is still marked as failed, in words or by a symbol
```

### Requirement: Light and dark
The system SHALL offer a light and a dark appearance and remember which the user chose.

#### Scenario: The choice is remembered

```gherkin
Given the user has chosen the dark appearance
When the user comes back later
Then the dashboard is shown in the dark appearance
```

### Requirement: Works on a narrow screen
The system SHALL keep every page usable on a screen as narrow as a phone's.

#### Scenario: A failure can be retried on a phone

```gherkin
Given the user opens the failures on a phone-sized screen
When the user retries a failed delivery
Then the delivery is retried
```

### Requirement: A quick way to anywhere
The system SHALL give the user a keyboard menu that leads to any page or flow by typing part of its name.

#### Scenario: The user jumps to a flow

```gherkin
Given the orders flow exists
When the user opens the keyboard menu and types "ord"
Then the orders flow is offered and can be opened
```

### Requirement: Safe against forged requests
The system SHALL refuse a change that does not come from the user's own signed-in page.

#### Scenario: A request forged from another site is refused

```gherkin
Given the user is signed in
When another site sends a request to retry a delivery in the user's name
Then the request is refused
```
