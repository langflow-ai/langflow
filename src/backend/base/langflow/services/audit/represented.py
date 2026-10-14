"""Audit-only identity asserted by an explicitly trusted authenticated credential."""

from __future__ import annotations

import base64
import binascii
import re
import unicodedata
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

from fastapi import HTTPException

from langflow.services.auth.context import AUTH_METHOD_API_KEY, get_current_auth_context
from langflow.services.database.models.audit_event.model import (
    REPRESENTED_ISSUER_MAX_LENGTH,
    REPRESENTED_SUBJECT_MAX_LENGTH,
)

if TYPE_CHECKING:
    from fastapi import Request

ISSUER_HEADER = "Langflow-Audit-Represented-Issuer"
SUBJECT_HEADER = "Langflow-Audit-Represented-Subject"
_ENCODED = re.compile(r"v1\.[A-Za-z0-9_-]+\Z")


@dataclass(frozen=True)
class RepresentedIdentity:
    issuer: str
    subject: str


current_represented_identity: ContextVar[RepresentedIdentity | None] = ContextVar(
    "langflow_audit_represented_identity", default=None
)


def _invalid() -> HTTPException:
    return HTTPException(
        status_code=400,
        detail="Invalid represented audit identity",
        headers={"X-Langflow-Error-Code": "INVALID_AUDIT_CONTEXT"},
    )


def decode_identity_value(encoded: str, limit: int) -> str:
    """Decode canonical v1 base64url UTF-8 without normalizing identity values."""
    if len(encoded) > 3 + 4 * ((4 * limit + 2) // 3) or not _ENCODED.fullmatch(encoded):
        raise _invalid()
    payload = encoded[3:]
    try:
        raw = base64.b64decode(payload + "=" * (-len(payload) % 4), altchars=b"-_", validate=True)
        value = raw.decode("utf-8")
    except (binascii.Error, UnicodeDecodeError, ValueError) as exc:
        raise _invalid() from exc
    if base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=") != payload:
        raise _invalid()
    if not value.strip() or len(value) > limit:
        raise _invalid()
    if any(unicodedata.category(char) in {"Cc", "Zl", "Zp"} for char in value):
        raise _invalid()
    return value


def bind_represented_identity(request: Request) -> None:
    """Validate after normal authentication and before any route mutation.

    The allowlist contains database API-key record UUIDs, never key material or
    user IDs. This identity is deliberately separate from authorization context.
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
    trusted = get_settings_service().settings.audit_trusted_api_key_ids
    if credential is None or credential.method != AUTH_METHOD_API_KEY or credential.api_key_id not in trusted:
        raise HTTPException(
            status_code=403,
            detail="Credential may not assert represented audit identity",
            headers={"X-Langflow-Error-Code": "REPRESENTED_IDENTITY_NOT_ALLOWED"},
        )
    identity = RepresentedIdentity(
        issuer=decode_identity_value(issuers[0], REPRESENTED_ISSUER_MAX_LENGTH),
        subject=decode_identity_value(subjects[0], REPRESENTED_SUBJECT_MAX_LENGTH),
    )
    current_represented_identity.set(identity)
