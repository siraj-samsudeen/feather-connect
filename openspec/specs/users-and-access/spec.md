# users-and-access

## Purpose
People and programs sign in, and each can do only what their role allows. An administrator looks after who has access, without a command line.

## Requirements

### Requirement: Sign in
The system SHALL let a user sign in with a name and a password, and refuse a wrong one without saying which of the two was wrong.

#### Scenario: A correct sign-in opens the dashboard

```gherkin
Given a user exists with a name and a password
When the user signs in with them
Then the overview is shown
```

#### Scenario: A wrong password is refused

```gherkin
Given a user exists with a name and a password
When the user signs in with a wrong password
Then the sign-in is refused
And the message does not say whether the name or the password was wrong
```

### Requirement: Roles
The system SHALL give each user one of four roles: a viewer looks; an operator also runs, retries, skips and replays; a developer also manages connections, budgets and alert rules; an administrator also manages users, tokens and packages.

#### Scenario: A viewer cannot retry

```gherkin
Given a user with the viewer role
When that user retries a failed delivery
Then the request is refused
```

#### Scenario: An operator can retry

```gherkin
Given a user with the operator role
When that user retries a failed delivery
Then the delivery is retried
```

#### Scenario: A developer can change a connection

```gherkin
Given a user with the developer role, in an environment that is not protected
When that user changes the address of the accounts service connection
Then the change is made
```

#### Scenario: An operator cannot change a connection

```gherkin
Given a user with the operator role
When that user changes the address of the accounts service connection
Then the request is refused
```

### Requirement: Two extra rights
The system SHALL give the right to decide holds, and the right to see personal data, only to users granted them.

#### Scenario: An operator without the grant cannot approve

```gherkin
Given a user with the operator role and no right to decide holds
When that user approves a waiting sale
Then the request is refused
```

### Requirement: Look after users
The system SHALL let an administrator add a user, reset a password and disable a user.

#### Scenario: A disabled user cannot sign in

```gherkin
Given an administrator has disabled a user who has left
When that user signs in
Then the sign-in is refused
```

### Requirement: A set password works once
The system SHALL accept a password set by an administrator for one sign-in, and then have the user choose their own.

#### Scenario: A new user chooses a password

```gherkin
Given an administrator has added a user with a first password
When the user signs in with it
Then the user is asked to choose a new password before going on
```

### Requirement: Change your own password
The system SHALL let any user change their own password.

#### Scenario: The new password works and the old one does not

```gherkin
Given the user is signed in
When the user changes their password
Then signing in with the new password works
And signing in with the old one is refused
```

### Requirement: Tokens for programs
The system SHALL let an administrator create a token for a program with a role and an end date, list the tokens, and revoke one.

#### Scenario: A revoked token stops working

```gherkin
Given a script uses a token to read the failures
When an administrator revokes that token
Then the script's next request is refused
```

#### Scenario: A token past its end date stops working

```gherkin
Given a token whose end date was yesterday
When it is used
Then the request is refused
```
