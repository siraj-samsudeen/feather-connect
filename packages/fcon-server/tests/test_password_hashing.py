"""Passwords are kept as argon2id hashes at OWASP's recommended strength (design point 3, ADR 0018).

The settings are stored with each hash.
"""

from argon2 import PasswordHasher

from fcon_server.users.passwords import hash_password, needs_rehash, password_matches


def test_a_hash_is_argon2id_at_19_mib_2_passes_1_lane():
    assert hash_password("blue-harbour-lamp").startswith("$argon2id$v=19$m=19456,t=2,p=1$")


def test_the_password_hashed_matches_its_hash():
    assert password_matches(hash_password("blue-harbour-lamp"), "blue-harbour-lamp")


def test_another_password_does_not_match():
    assert not password_matches(hash_password("blue-harbour-lamp"), "letmein")


def test_no_hash_matches_no_password():
    """A name nobody has: the check still runs, against a dummy hash."""
    assert not password_matches(None, "blue-harbour-lamp")


def test_a_hash_that_is_not_argon2_matches_nothing():
    assert not password_matches("not a hash", "blue-harbour-lamp")


def test_a_hash_made_weaker_than_now_is_redone():
    weaker = PasswordHasher(time_cost=1, memory_cost=8192, parallelism=1).hash("blue-harbour-lamp")

    assert needs_rehash(weaker)


def test_a_hash_made_now_is_kept():
    assert not needs_rehash(hash_password("blue-harbour-lamp"))
