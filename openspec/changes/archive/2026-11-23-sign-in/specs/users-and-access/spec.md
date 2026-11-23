# Users and access

## MODIFIED Requirements

### Requirement: A refused sign-in gives no hint
The system SHALL refuse a sign-in with a wrong user name or password without saying which of the two was wrong.

#### Scenario: The refusal does not say which part was wrong

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user is not signed in
When the user signs in as "ann" with the password "letmein"
Then the sign-in is refused
And the user is told the user name or password is wrong, without being told which
And the page's title says the sign-in failed
```

#### Scenario: A name nobody has is refused in the same words

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user is not signed in
When the user signs in as "alex" with the password "blue-harbour-lamp"
Then the sign-in is refused
And the user is told the user name or password is wrong, without being told which
```

## ADDED Requirements

### Requirement: The first administrator from the command line
The system SHALL let whoever installs it make its first user from the command line, and SHALL make the first user an administrator, so there is never a user but no administrator.

#### Scenario: The first user is an administrator

```gherkin
Given a new install with no users
When the operator adds the user "ann" from the command line, with the password "blue-harbour-lamp"
And the user signs in as "ann" with the password "blue-harbour-lamp"
Then the user sees the overview
And the user is shown as "ann", an administrator
```

### Requirement: The first administrator from a setting
The system SHALL, on a host where commands are awkward, make the first administrator named in its settings when it starts with no users, with a one-time password that only its log shows, once.

#### Scenario: The log gives a one-time password once

```gherkin
Given a new install with no users
And the product's settings name "ann" as the first administrator
When the operator starts the product
Then its log gives a one-time password for "ann", and says to sign in and choose a new one
And after a restart its log gives no password again
```

### Requirement: Sign in
The system SHALL let a user who gives their user name and password sign in, and keep them signed in from page to page.

#### Scenario: Signed in, the user sees the overview

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user is not signed in
When the user signs in as "ann" with the password "blue-harbour-lamp"
Then the user sees the overview
And the user is still signed in when they open the dashboard again
```

### Requirement: Back to the page asked for
The system SHALL, after a sign-in, take the user back to the dashboard page they had asked for, and to the overview when the page asked for is on another site.

#### Scenario: Back at the page asked for

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user is not signed in
When the user opens the address of run 42
And signs in as "ann" with the password "blue-harbour-lamp"
Then the user is at the address of run 42
```

#### Scenario: A link to another site leads to the overview

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user is not signed in
When the user follows a sign-in link that would send them on to another site
And signs in as "ann" with the password "blue-harbour-lamp"
Then the user sees the overview
```

### Requirement: A given password works once
The system SHALL accept a password the user was given, by the operator or in the log, for one sign-in, and ask the user to choose their own before any other page opens. The first user's password, typed by whoever installs the product, is their own and works on.

#### Scenario: A new user chooses their own password

```gherkin
Given "ben@example.com" was added as an operator with the first password "given-once-0001"
When the user signs in as "ben@example.com" with the password "given-once-0001"
Then the user is asked to choose their own password before going on
And the user sees the overview once they have chosen "ben-own-password-1"
```

#### Scenario: Every page leads to choosing a password first

```gherkin
Given "ben@example.com" was added as an operator with the first password "given-once-0001"
And the user has signed in as "ben@example.com" with the password "given-once-0001"
When the user opens the dashboard without choosing a password
Then the user is asked to choose their own password before going on
```

#### Scenario: The given password works only once

```gherkin
Given "ben@example.com" was added as an operator with the first password "given-once-0001"
And the user has signed in as "ben@example.com" and chosen the password "ben-own-password-1"
When the user signs out, and signs in as "ben@example.com" with the password "given-once-0001"
Then the sign-in is refused
```

### Requirement: Passwords hard to guess
The system SHALL refuse a password that is short, very common or the user's own name, and say which rule it broke; it SHALL ask for no particular mix of characters.

#### Scenario Outline: A weak password is refused, saying why

```gherkin
Given "ben@example.com" was added as an operator with the first password "given-once-0001"
And the user has signed in as "ben@example.com" with the password "given-once-0001"
When the user chooses the password "<password>"
Then the password is refused, because it is <reason>
And the user is still asked to choose their own password

Examples:
  | password       | reason             |
  | short-one      | too short          |
  | password123456 | too common         |
  | ben@example.com | the user's own name |
```

### Requirement: Signing out ends every session
The system SHALL end every session of a user (each browser they are signed in on) when they sign out, choose a new password, or are disabled.

#### Scenario: Signing out on one computer signs out the other

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user is signed in as "ann" on two computers
When the user signs out on one of them
Then the user is no longer signed in on the other
```

#### Scenario: A new password signs out the other computer

```gherkin
Given "ben@example.com" was added as an operator with the first password "given-once-0001"
And the user has signed in as "ben@example.com" with the password "given-once-0001" on two computers
When the user chooses the password "ben-own-password-1" on one of them
Then the user is no longer signed in on the other
```

#### Scenario: A disabled user is signed out at once

```gherkin
Given "ben@example.com" is an operator with the password "ben-own-password-1"
And the user is signed in as "ben@example.com"
When the operator disables "ben@example.com" from the command line
Then the user is no longer signed in
And signing in as "ben@example.com" with the password "ben-own-password-1" is refused
```

### Requirement: Sessions run out
The system SHALL end a session left unused for 12 hours, and any session 7 days after its sign-in.

#### Scenario: A session left for a night has ended

```gherkin
Given the user is signed in as "ann"
When the user comes back after 13 hours without using the dashboard
Then the user is asked to sign in again
```

### Requirement: Guessing is slowed
The system SHALL, after 3 failed sign-ins in 15 minutes for one user name or from one address, make each further attempt wait longer, up to a minute, and SHALL never lock anyone out.

#### Scenario: Even the right password waits after repeated failures

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And someone has failed to sign in as "ann" 3 times in a row
When the user signs in as "ann" with the password "blue-harbour-lamp" at once
Then the sign-in is refused, in the same words as a wrong password
And signing in as "ann" with the password "blue-harbour-lamp" works once the wait has passed
```

#### Scenario: Guessing other names from one address is slowed too

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And someone at the user's address has failed to sign in as 3 different names
When the user signs in as "ann" with the password "blue-harbour-lamp" at once
Then the sign-in is refused, in the same words as a wrong password
```

### Requirement: Forged forms are refused
The system SHALL refuse a form that was not sent from a page it showed in the same session, tell the user the form has expired, and do nothing it asked.

#### Scenario: An old page's form is refused as expired

```gherkin
Given the user is signed in as "ann", with the overview open
And the user has since signed out and back in from another tab
When the user signs out from the overview opened before
Then the user is told the form has expired, and to reload the page
And the user can go on to the overview from there
And the user is still signed in
```

#### Scenario: A form sent from another site is refused

```gherkin
Given the user is signed in as "ann"
When a page on another site sends the dashboard a sign-out form
Then the form is refused as expired
And the user is still signed in
```

### Requirement: Look after users from the command line
The system SHALL let the operator add, list, disable and enable users and change their role from the command line; a change of role holds from the user's next page.

#### Scenario: A new role shows at once

```gherkin
Given "ben@example.com" is an operator with the password "ben-own-password-1"
And the user is signed in as "ben@example.com"
When the operator makes "ben@example.com" a viewer from the command line
And the user opens the dashboard again
Then the user is shown as "ben@example.com", a viewer
```

#### Scenario: A user enabled again gets in

```gherkin
Given "ben@example.com" is an operator with the password "ben-own-password-1"
And the operator has disabled "ben@example.com" from the command line
When the operator enables "ben@example.com" from the command line
And the user signs in as "ben@example.com" with the password "ben-own-password-1"
Then the user sees the overview
```

### Requirement: Always an administrator
The system SHALL refuse to disable or demote the last active administrator, and say why.

#### Scenario: The only administrator keeps the role

```gherkin
Given "ann" is the only administrator
When the operator makes "ann" an operator from the command line
Then the change is refused, because "ann" is the only administrator
And "ann" is still an administrator
```

#### Scenario: The only administrator cannot be disabled

```gherkin
Given "ann" is the only administrator
When the operator disables "ann" from the command line
Then the change is refused, because "ann" is the only administrator
```

### Requirement: Every sign-in is recorded
The system SHALL record in the audit log (a record of who did what, which nobody can change) every sign-in, refused sign-in, sign-out, password change and change to a user, with the visitor's address, and SHALL never record a password.

#### Scenario: A refused and a good sign-in are both recorded

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
When the user signs in as "ann" with the password "letmein"
And signs in as "ann" with the password "blue-harbour-lamp"
Then the audit log records a refused and a successful sign-in for "ann", from the user's address
And no password appears anywhere in the audit log
```
