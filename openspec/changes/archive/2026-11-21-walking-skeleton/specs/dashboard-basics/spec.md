# Dashboard basics

## Purpose

Promises that hold on every page of the dashboard, so that other specs need not repeat them.

## ADDED Requirements

### Requirement: Pages work without scripts
The system SHALL keep its pages working, forms included, when scripts are switched off in the browser.

#### Scenario: A refused sign-in is explained with scripts off

```gherkin
Given nobody has been given access yet
And the user has switched scripts off in the browser
When the user signs in as "alex" with the password "letmein"
Then the sign-in is refused
And the user is told the user name or password is wrong, without being told which
And the page's title says the sign-in failed
```

### Requirement: Light and dark
The system SHALL show a light and a dark appearance, following the setting of the user's computer.

#### Scenario: The dashboard is dark when the computer is

```gherkin
Given the user's computer is set to the dark appearance
When the user opens the sign-in page
Then the page is shown in the dark appearance
```

### Requirement: Accessible in light and dark
The system SHALL meet the web's accessibility standard, WCAG 2.1, at its middle level, AA, in its light and its dark appearance.

#### Scenario Outline: No accessibility problem in either appearance

```gherkin
Given the user's computer is set to the <appearance> appearance
When the user opens the sign-in page, a refused sign-in and a page that does not exist
Then an automatic accessibility check finds no problem on any of them

Examples:
  | appearance |
  | light |
  | dark |
```

### Requirement: A missing page says so
The system SHALL answer an address it does not have with a page that says the page was not found, and offers the way to sign in.

#### Scenario: A missing page says it was not found

```gherkin
Given the user is not signed in
When the user opens the address of run 42, which the dashboard does not have
Then the user is told the page was not found
And the user can go on to the sign-in page from there
```
