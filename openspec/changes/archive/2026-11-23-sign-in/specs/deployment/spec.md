# Deployment

## MODIFIED Requirements

### Requirement: Runs from its image
The system SHALL run from its container image, taking its settings, such as its database's address and its secret key, from the place it runs.

#### Scenario: Ready with only a database address

```gherkin
Given a new, empty Postgres 18 database
When the operator upgrades the database with the product's image
And starts the product's image, giving it only the database's address, and the secret key every install needs
Then the product answers that it is ready to take work
And it shows the sign-in page
```

### Requirement: Follows the host's port
The image SHALL follow the port its host gives it, both to answer and for its health check: the check by which the container runtime sees, by itself, whether the product is running.

#### Scenario: Healthy on the host's port

```gherkin
Given a new, empty Postgres 18 database
And a host that gives the product the port 9090
When the operator upgrades the database with the product's image
And starts the product's image, giving it only the database's address, and the secret key every install needs
Then the product answers on port 9090 that it is running
And the container runtime reports the product as healthy
```

## ADDED Requirements

### Requirement: Refuses to start without its secret key
The system SHALL refuse to start without a secret key (a long random value only its operator knows, which keeps its sign-in safe), or with one too short to be safe, and say how to make one.

#### Scenario: A missing secret key is explained

```gherkin
Given a new, empty Postgres 18 database
When the operator upgrades the database with the product's image
And starts the product's image, giving it only the database's address
Then the product does not start
And it says the secret key is missing, and how to make one
```

### Requirement: A new secret key signs nobody out
The system SHALL accept, for a few minutes, what its previous secret key signed, when the operator replaces the key and names the old one as previous, so a leaked key can be replaced without interrupting anyone.

#### Scenario: A sign-in started under the old key still works

```gherkin
Given "ann" is an administrator with the password "blue-harbour-lamp"
And the user has the sign-in page open
When the operator restarts the product with a new secret key, naming the old one as previous
And the user signs in as "ann" with the password "blue-harbour-lamp"
Then the user sees the overview
```

### Requirement: The visitor's own address behind a proxy
The system SHALL see each visitor's own address, rather than the proxy's, when the operator has said which proxy to trust, and SHALL warn in its log when a proxy's word is ignored because no proxy is trusted.

#### Scenario: Behind the standard setup's proxy, the visitor's address is recorded

```gherkin
Given the standard setup is running on one machine
And "ann" is an administrator with the password "blue-harbour-lamp"
When the user signs in as "ann" through the site's encrypted address
Then the audit log records the sign-in from the user's own address, not the proxy's
```

#### Scenario: An untrusted proxy is named in the log

```gherkin
Given a new, empty Postgres 18 database
And the product's image runs with no proxy trusted
When a visitor opens two pages through a proxy that names the visitor's address
Then its log warns once, not twice, that no proxy is trusted, and names the setting to trust one
```
