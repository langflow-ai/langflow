"""TOTP (Time-based One-Time Password) utilities for two-factor authentication.

Uses PyOTP for RFC 6238 compliant TOTP, compatible with Google Authenticator and Authy.
Secrets are encrypted at rest using Fernet (derived from the application SECRET_KEY).

Security notes
--------------
* Replay attack prevention: each successfully verified code is placed in a TTLCache
  keyed by ``(user_id, code, time_window)`` for 90 s (3 windows).  A second call with
  the same code within that window will be rejected even if the OTP is still valid.
  The cache is process-local; for multi-process deployments a shared Redis store should
  replace it.
* Single-use partial tokens: partial tokens are burned (SHA-256 hash stored in
  ``_burnt_partial_tokens``) after either a successful TOTP verification or
  ``MAX_VERIFY_ATTEMPTS`` consecutive failures.  This prevents an attacker who captures
  the partial token from making unlimited guesses at the 6-digit code.
* Clock drift: ``valid_window=1`` accepts codes ±1 period (±30 s) of the server clock.
* Secret storage: secrets are Fernet-encrypted using the application SECRET_KEY before
  being persisted to the database.
"""

from __future__ import annotations

import binascii
import hashlib
import time

import pyotp
from cachetools import TTLCache

TOTP_ISSUER = "Langflow"
TOTP_VALID_WINDOW = 1  # Allow ±1 period (±30 seconds) of clock drift
TOTP_WINDOW_SECONDS = 30
# Keep entries for 3 windows so that a code valid across a window boundary is still blocked.
_REPLAY_TTL = TOTP_WINDOW_SECONDS * (2 * TOTP_VALID_WINDOW + 1)

# How many wrong codes are allowed before the partial token is burned entirely.
MAX_VERIFY_ATTEMPTS = 5

# TTL for partial-token state caches must cover the full partial-token lifetime (5 min).
_PARTIAL_TOKEN_TTL = 5 * 60 + 10  # 5 min 10 s — slight slack for clock skew

# Process-local anti-replay cache; keyed by "<user_id>:<code>:<window_index>"
_used_codes: TTLCache = TTLCache(maxsize=10_000, ttl=_REPLAY_TTL)

# Burned partial-token hashes (after success or too many failures).
# Key: SHA-256 hex digest of the raw partial_token string.
_burnt_partial_tokens: TTLCache = TTLCache(maxsize=50_000, ttl=_PARTIAL_TOKEN_TTL)

# Failed-attempt counters per partial token.
# Key: SHA-256 hex digest; Value: int (failure count).
_partial_token_failures: TTLCache = TTLCache(maxsize=50_000, ttl=_PARTIAL_TOKEN_TTL)


def _current_window() -> int:
    """Return the index of the current 30-second TOTP time window."""
    return int(time.time()) // TOTP_WINDOW_SECONDS


def _token_hash(partial_token: str) -> str:
    """Return a short SHA-256 hex digest of a partial token for cache keying."""
    return hashlib.sha256(partial_token.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Per-code replay prevention
# ---------------------------------------------------------------------------


def is_replay(user_id: str, code: str) -> bool:
    """Return True if this (user, code) pair was already used in the current window."""
    window = _current_window()
    for offset in range(-TOTP_VALID_WINDOW, TOTP_VALID_WINDOW + 1):
        key = f"{user_id}:{code}:{window + offset}"
        if key in _used_codes:
            return True
    return False


def mark_used(user_id: str, code: str) -> None:
    """Record that this code has been consumed so it cannot be replayed."""
    window = _current_window()
    for offset in range(-TOTP_VALID_WINDOW, TOTP_VALID_WINDOW + 1):
        key = f"{user_id}:{code}:{window + offset}"
        _used_codes[key] = True


# ---------------------------------------------------------------------------
# Partial-token lifecycle (single-use + failed-attempt cap)
# ---------------------------------------------------------------------------


def is_partial_token_burnt(partial_token: str) -> bool:
    """Return True if this partial token has already been used or exhausted."""
    return _token_hash(partial_token) in _burnt_partial_tokens


def burn_partial_token(partial_token: str) -> None:
    """Permanently invalidate a partial token (success or too many failures)."""
    _burnt_partial_tokens[_token_hash(partial_token)] = True


def record_partial_token_failure(partial_token: str) -> int:
    """Increment the failure counter for a partial token and return the new count.

    Automatically burns the token once MAX_VERIFY_ATTEMPTS is reached.
    """
    key = _token_hash(partial_token)
    count: int = _partial_token_failures.get(key, 0) + 1
    if count >= MAX_VERIFY_ATTEMPTS:
        burn_partial_token(partial_token)
        _partial_token_failures.pop(key, None)
    else:
        _partial_token_failures[key] = count
    return count


def generate_totp_secret() -> str:
    """Generate a cryptographically secure base32 TOTP secret."""
    return pyotp.random_base32()


def is_valid_base32(value: str) -> bool:
    """Return True if *value* is a non-empty, valid base32 string."""
    if not value:
        return False
    try:
        import base64

        base64.b32decode(value.upper())
    except (binascii.Error, ValueError):
        return False
    else:
        return True


def get_provisioning_uri(raw_secret: str, username: str) -> str:
    """Return an otpauth:// URI suitable for QR code display.

    Compatible with Google Authenticator, Authy, and all RFC 6238 clients.
    """
    totp = pyotp.TOTP(raw_secret)
    return totp.provisioning_uri(name=username, issuer_name=TOTP_ISSUER)


def verify_totp_code(raw_secret: str, code: str) -> bool:
    """Verify a 6-digit TOTP code against the raw (unencrypted) secret.

    Returns False for empty inputs or a malformed (non-base32) secret.
    Does NOT check the replay cache — callers are responsible for calling
    ``is_replay`` / ``mark_used`` around this function.
    """
    if not raw_secret or not code:
        return False
    if not is_valid_base32(raw_secret):
        return False
    try:
        totp = pyotp.TOTP(raw_secret)
        return bool(totp.verify(code, valid_window=TOTP_VALID_WINDOW))
    except Exception:  # noqa: BLE001
        return False


def encrypt_totp_secret(raw_secret: str) -> str:
    """Encrypt a TOTP secret for storage using the application Fernet key."""
    from langflow.services.deps import get_auth_service

    auth_service = get_auth_service()
    return auth_service.encrypt_api_key(raw_secret)


def decrypt_totp_secret(encrypted_secret: str) -> str:
    """Decrypt a stored TOTP secret."""
    from langflow.services.deps import get_auth_service

    auth_service = get_auth_service()
    return auth_service.decrypt_api_key(encrypted_secret)
