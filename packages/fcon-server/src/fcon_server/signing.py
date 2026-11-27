"""What the secret key signs (design point 6): short-lived values made before a session exists.

The sign-in form's token is one. HMAC-SHA-256 from the standard library. A value
signed by FCON_SECRET_KEY_PREVIOUS is accepted too, so a key can be replaced
without signing anyone out of the form.
"""

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta

SIGN_IN_TOKEN_LIFE = timedelta(hours=2)


@dataclass(frozen=True)
class SecretKeys:
    """The key that signs, and the previous one, still accepted while a key is replaced."""

    current: str
    previous: str | None = None

    def __repr__(self) -> str:  # never in a log or a traceback's locals
        return "SecretKeys(...)"


def _signature(key: str, text: str) -> str:
    """The HMAC-SHA-256 signature of `text` under `key`, in hex."""
    return hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()


def make_sign_in_token(keys: SecretKeys, now: datetime) -> str:
    """A new sign-in token, `<random>.<unix seconds>.<signature>`: the cookie's value and the form's."""
    text = f"{secrets.token_urlsafe(32)}.{int(now.timestamp())}"
    return f"{text}.{_signature(keys.current, text)}"


def sign_in_token_valid(keys: SecretKeys, token: str, now: datetime) -> bool:
    """Whether `token` is signed by the current or previous key and at most SIGN_IN_TOKEN_LIFE old."""
    value, _, rest = token.partition(".")
    seconds, _, signature = rest.partition(".")
    if not (value and seconds.isdigit() and signature):
        return False
    age = now.timestamp() - int(seconds)
    if not 0 <= age <= SIGN_IN_TOKEN_LIFE.total_seconds():
        return False
    text = f"{value}.{seconds}"
    candidates = [keys.current, *([keys.previous] if keys.previous else [])]
    return any(hmac.compare_digest(_signature(key, text), signature) for key in candidates)
