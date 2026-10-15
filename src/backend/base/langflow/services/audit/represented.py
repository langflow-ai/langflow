"""Audit-only identity asserted by an explicitly trusted authenticated credential."""

from __future__ import annotations

import base64
import binascii
import re
import secrets
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from langflow.services.auth.context import AUTH_METHOD_API_KEY, get_current_auth_context
from langflow.services.database.models.audit_event.model import (
    REPRESENTED_ISSUER_MAX_LENGTH,
    REPRESENTED_SUBJECT_MAX_LENGTH,
)

if TYPE_CHECKING:
    from fastapi import Request

ISSUER_HEADER = "Langflow-Audit-Represented-Issuer"
SUBJECT_HEADER = "Langflow-Audit-Represented-Subject"
_ENCODING_PREFIX = "v1."
# The largest field is the issuer: 2048 characters can require 8192 UTF-8
# bytes, which encode to 10923 unpadded base64 characters plus the "v1." prefix.
_MAX_ENCODED_HEADER_LENGTH = 10_926
_BASE64_BLOCK_CHARACTERS = 4
_ENCODED = re.compile(rf"{re.escape(_ENCODING_PREFIX)}[A-Za-z0-9_-]+\Z")
_FORBIDDEN_CATEGORIES = frozenset({"Cc", "Cf", "Zl", "Zp"})


class AuditIdentityError(ValueError):
    """An asserted audit identity violates the trust or transport contract."""


class InvalidAuditContextError(AuditIdentityError):
    """The represented identity cannot be decoded or safely recorded."""


class UntrustedAuditIdentityError(AuditIdentityError):
    """The authenticated credential cannot assert represented identity."""

    def __init__(self) -> None:
        super().__init__("Credential may not assert represented audit identity")


@dataclass(frozen=True)
class RepresentedIdentity:
    issuer: str
    subject: str


current_represented_identity: ContextVar[RepresentedIdentity | None] = ContextVar(
    "langflow_audit_represented_identity", default=None
)


def _invalid() -> InvalidAuditContextError:
    return InvalidAuditContextError("Invalid represented audit identity")


def decode_identity_value(encoded: str, character_limit: int) -> str:
    """Read the v1. prefix and decode ASCII base64url into the original UTF-8 identity."""
    if len(encoded) > _MAX_ENCODED_HEADER_LENGTH or not _ENCODED.fullmatch(encoded):
        raise _invalid()
    payload = encoded[len(_ENCODING_PREFIX) :]
    try:
        padded_payload = payload + "=" * (-len(payload) % _BASE64_BLOCK_CHARACTERS)
        raw = base64.b64decode(padded_payload, altchars=b"-_", validate=True)
        value = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise _invalid() from exc
    if not value.strip() or len(value) > character_limit:
        raise _invalid()
    if any(unicodedata.category(char) in _FORBIDDEN_CATEGORIES for char in value):
        raise _invalid()
    return value


def bind_represented_identity(request: Request) -> None:
    """Validate after normal authentication and before any route mutation.

    The record allowlist uses database API-key UUIDs. Secret-backed trust matches
    a fingerprint from successful database authentication. Neither changes authorization.
    """
    from langflow.services.deps import get_settings_service

    current_represented_identity.set(None)
    issuers = request.headers.getlist(ISSUER_HEADER)
    subjects = request.headers.getlist(SUBJECT_HEADER)
    if not issuers and not subjects:
        return
    if len(issuers) != 1 or len(subjects) != 1:
        raise _invalid()
    credential = get_current_auth_context()
    settings = get_settings_service().settings
    trusted = False
    if credential is not None and credential.method == AUTH_METHOD_API_KEY and credential.api_key_id is not None:
        trusted = credential.api_key_id in settings.audit_trusted_api_key_ids
        if settings.audit_trusted_api_key is not None and credential.api_key_fingerprint is not None:
            from langflow.services.database.models.api_key.crud import hash_api_key

            configured = hash_api_key(settings.audit_trusted_api_key.get_secret_value())
            trusted = trusted or secrets.compare_digest(credential.api_key_fingerprint, configured)
    if not trusted:
        raise UntrustedAuditIdentityError
    identity = RepresentedIdentity(
        issuer=decode_identity_value(issuers[0], REPRESENTED_ISSUER_MAX_LENGTH),
        subject=decode_identity_value(subjects[0], REPRESENTED_SUBJECT_MAX_LENGTH),
    )
    current_represented_identity.set(identity)
