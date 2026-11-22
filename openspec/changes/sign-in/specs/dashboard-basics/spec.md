# Dashboard basics

## ADDED Requirements

### Requirement: Every page says where and who
The system SHALL show, on every page a signed-in user sees, the name of the environment (such as development or production) and who is signed in, with their role.

#### Scenario: The overview names the environment and the user

```gherkin
Given the product's environment is named "staging"
And the user is signed in as "ann", an administrator
When the user opens the dashboard
Then the page names the environment "staging"
And the user is shown as "ann", an administrator
```

## MODIFIED Requirements

### Requirement: Accessible in light and dark
The system SHALL meet the web's accessibility standard, WCAG 2.1, at its middle level, AA, in its light and its dark appearance.

#### Scenario Outline: No accessibility problem in either appearance

```gherkin
Given the user's computer is set to the <appearance> appearance
When the user opens the sign-in page, a refused sign-in and a page that does not exist
And the user opens the overview, the page to choose a password and an expired form
Then an automatic accessibility check finds no problem on any of them

Examples:
  | appearance |
  | light |
  | dark |
```
