"""Bcrypt password hashing compatible with existing Passlib hashes."""

import bcrypt

_BCRYPT_PASSWORD_BYTES = 72
_MAX_PASSWORD_BYTES = 4096


def _as_bytes(value: str | bytes) -> bytes:
    if isinstance(value, str):
        return value.encode("utf-8")
    if isinstance(value, bytes):
        return value
    msg = "Password and hash values must be strings or bytes"
    raise TypeError(msg)


class PasswordContext:
    """Keep Passlib's bcrypt format and password limits without Passlib."""

    @staticmethod
    def hash(secret: str | bytes) -> str:
        """Hash a password with the same bcrypt cost and truncation as Passlib."""
        secret_bytes = _as_bytes(secret)
        if len(secret_bytes) > _MAX_PASSWORD_BYTES:
            msg = "Password exceeds maximum allowed size"
            raise ValueError(msg)
        if b"\x00" in secret_bytes:
            msg = "Password contains a null byte"
            raise ValueError(msg)
        # Passlib 1.7.4 and bcrypt 4.0.1 silently used the first 72 UTF-8 bytes.
        return bcrypt.hashpw(secret_bytes[:_BCRYPT_PASSWORD_BYTES], bcrypt.gensalt(rounds=12)).decode("ascii")

    @staticmethod
    def verify(secret: str | bytes, hashed_secret: str | bytes) -> bool:
        """Verify both new and stored Passlib bcrypt hashes."""
        try:
            secret_bytes = _as_bytes(secret)
            if len(secret_bytes) > _MAX_PASSWORD_BYTES or b"\x00" in secret_bytes:
                return False
            return bcrypt.checkpw(secret_bytes[:_BCRYPT_PASSWORD_BYTES], _as_bytes(hashed_secret))
        except (TypeError, ValueError):
            return False
