# Users and access

## Purpose

Who may use the dashboard. Nobody has been given access yet, so the sign-in page is there and
every attempt is refused.

## Requirements

### Requirement: Sign in first
The system SHALL show the sign-in page to someone who opens the dashboard's front page without being signed in.

#### Scenario: The dashboard opens on the sign-in page

```gherkin
Given the user is not signed in
When the user opens the dashboard
Then the sign-in page names the product
And it asks for the user's name and password, with a button to sign in
```

### Requirement: A refused sign-in gives no hint
The system SHALL refuse a sign-in with a wrong user name or password without saying which of the two was wrong.

#### Scenario: The refusal does not say which part was wrong

```gherkin
Given the user is not signed in
And nobody has been given access yet
When the user signs in as "alex" with the password "letmein"
Then the sign-in is refused
And the user is told the user name or password is wrong, without being told which
And the page's title says the sign-in failed
```
