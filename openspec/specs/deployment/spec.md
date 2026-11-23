# Deployment

## Purpose
The operator (the person who runs the product on a host) runs it from its container image: a
packaged copy of the product, with all it needs, that a container runtime such as Docker starts.
The image runs on a cloud host that runs containers, or on one machine in the standard setup,
which adds a proxy: a program in front of the product that encrypts its traffic, at the site's
name the operator chooses (such as connect.example.com). Either way the database is a Postgres 18
server run outside the product, often shared with other apps, where an administrator has made the
product its own database. Before a version of the product starts, its database is upgraded:
given the changes that version needs. The image is built for both common kinds of processor, and
holds no secret: each place it runs gives it its own settings.

## Requirements

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

### Requirement: Upgrades its database by itself
The standard setup SHALL bring its database up to date by itself, before it starts the product.

#### Scenario: Ready on a new database

```gherkin
Given the standard setup on one machine, with a new, empty database
When the operator starts it
Then the product answers that it is ready to take work, with no upgrade run by hand
And the upgrade had finished before the product started
```

### Requirement: Reached only through its proxy
The standard setup SHALL let visitors reach the product only through its proxy, over encrypted connections, with a certificate (the proof of the site's identity that a browser checks) that the proxy gets by itself.

#### Scenario: The sign-in page arrives encrypted

```gherkin
Given the standard setup on one machine, with its site's name but no certificate
When the operator starts it
Then the sign-in page is served over an encrypted connection
And no other part of the setup can be reached from outside the machine
```

#### Scenario: A plain address leads to the encrypted one

```gherkin
Given the standard setup is running on one machine
When the operator opens the site's plain, unencrypted address
Then the operator is sent on to the site's encrypted address
```

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
