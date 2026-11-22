"""The users service (sign-in, design § How it is built): the one place for
every rule about users. The rights table and `require`, user names, password
rules and hashing, sessions and the first administrator. The pages and
`fcon users` call it with a context; neither talks to the store directly."""
