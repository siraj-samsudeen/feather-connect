"""Password hashing (design point 3, ADR 0018): argon2id through argon2-cffi at OWASP's strength.

OWASP's recommended strength: 19 MiB, 2 passes, 1 lane. Its settings are stored in each hash, so
a hash made weaker is redone at the next sign-in.
"""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_HASHER = PasswordHasher(time_cost=2, memory_cost=19 * 1024, parallelism=1)
# What a name nobody has is checked against, so that it takes as long as a
# real one (design point 7).
_DUMMY_HASH = _HASHER.hash("a password nobody has")


def hash_password(password: str) -> str:
    """The password's argon2id hash, its settings and a random salt in it."""
    return _HASHER.hash(password)


def password_matches(password_hash: str | None, password: str) -> bool:
    """Whether the password matches the hash; False when there is no hash.

    Always one argon2id check: against the dummy hash when there is none.
    """
    try:
        return _HASHER.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except VerificationError, InvalidHashError:
        return False


def needs_rehash(password_hash: str) -> bool:
    """Whether the hash was made with other settings than today's, so it should be redone."""
    return _HASHER.check_needs_rehash(password_hash)
