# Deployment

## Purpose

The operator (the person who runs the product on a host) runs it from its container image: a
packaged copy of the product, with all it needs, that a container runtime such as Docker starts.
The image runs on a cloud host that runs containers, or on one machine in the standard setup,
which adds the database and a proxy: a program in front of the product that encrypts its traffic,
at the site's name the operator chooses (such as connect.example.com). Before a version of the
product starts, its database is upgraded: given the changes that version needs. The image is
built for both common kinds of processor, and holds no secret: each place it runs gives it its
own settings.

## ADDED Requirements

### Requirement: Runs from its image
The system SHALL run from its container image, taking its settings, such as its database's address, from the place it runs.

#### Scenario: Ready with only a database address

```gherkin
Given a new, empty Postgres 18 database
When the operator upgrades the database with the product's image
And starts the product's image, giving it only the database's address
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
And starts the product's image, giving it only the database's address
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

### Requirement: Keeps its data
The standard setup SHALL keep its database's data when its containers are removed and started again, as on an upgrade of the product.

#### Scenario: The data outlives the containers

```gherkin
Given the standard setup has been running on one machine
When the operator removes its containers and starts it again
Then the setup's upgrade says the database was already up to date
```
