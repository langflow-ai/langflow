"""Helper utilities for encoding and decoding Langflow API keys.

This module provides a thin abstraction around the token format used for
Langflow API keys. The goal is to keep the format backwards compatible
with the existing ``sk-<random>`` keys while allowing additional metadata
(e.g. organisation and user identifiers) to be embedded when Clerk-based
multi-organisation authentication is enabled.
"""

from __future__ import annotations

import base64
import json
import secrets
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from langflow.services.auth.clerk_utils import auth_header_ctx
from langflow.services.deps import get_settings_service

if TYPE_CHECKING:
    from uuid import UUID

API_KEY_PREFIX = "sk-"


@dataclass(frozen=True)
class ApiKeyPayload:
    """Decoded information extracted from an API key."""

    organization_id: str | None
    user_id: str | None
    nonce: str | None
    is_encoded: bool


def _encode_payload(payload: dict[str, str]) -> str:
    """Encode the payload to a compact base64url string."""
    serialized = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    token = base64.urlsafe_b64encode(serialized.encode()).decode()
    return token.rstrip("=")


def _decode_payload(encoded: str) -> dict[str, str] | None:
    """Decode a payload from its base64url form.

    Returns ``None`` when the input is not a valid payload encoded by
    :func:`encode_api_key`.
    """
    padding = "=" * (-len(encoded) % 4)
    try:
        decoded = base64.urlsafe_b64decode(encoded + padding)
        data = json.loads(decoded.decode())
    except (ValueError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    else:
        if not isinstance(data, dict):
            return None
        if data.get("v") != 1:
            return None
        return data  # type: ignore[return-value]


def encode_api_key(*, user_id: str, organization_id: str | None) -> str:
    """Create a new API key string.

    When an ``organization_id`` is supplied the resulting token embeds the
    organisation identifier alongside the user identifier and a random nonce.
    If ``organization_id`` is ``None`` the legacy ``sk-<random>`` format is
    returned to remain backwards compatible.
    """
    nonce = secrets.token_urlsafe(32)
    if not organization_id:
        return f"{API_KEY_PREFIX}{nonce}"

    payload = {
        "v": 1,
        "org": organization_id,
        "usr": user_id,
        "nonce": nonce,
    }
    encoded = _encode_payload(payload)
    return f"{API_KEY_PREFIX}{encoded}"


def decode_api_key(api_key: str) -> ApiKeyPayload:
    """Attempt to decode an API key.

    The function never raises and instead signals whether decoding
    succeeded via the ``is_encoded`` field of the returned
    :class:`ApiKeyPayload` object.
    """
    if not api_key or not api_key.startswith(API_KEY_PREFIX):
        return ApiKeyPayload(organization_id=None, user_id=None, nonce=None, is_encoded=False)

    encoded_payload = api_key[len(API_KEY_PREFIX) :]
    data = _decode_payload(encoded_payload)
    if data is None:
        return ApiKeyPayload(organization_id=None, user_id=None, nonce=None, is_encoded=False)

    return ApiKeyPayload(
        organization_id=data.get("org"),
        user_id=data.get("usr"),
        nonce=data.get("nonce"),
        is_encoded=True,
    )


def generate_api_key_for_user(user_id: UUID | str) -> str:
    """Generate an API key for ``user_id`` honouring Clerk configuration."""
    settings_service = get_settings_service()
    if not settings_service.auth_settings.CLERK_AUTH_ENABLED:
        return f"{API_KEY_PREFIX}{secrets.token_urlsafe(32)}"

    payload = auth_header_ctx.get() or {}
    organization_id = payload.get("org_id") if isinstance(payload, dict) else None
    return encode_api_key(user_id=str(user_id), organization_id=organization_id)


def apply_api_key_context(
    api_key: str,
    *,
    expected_user_id: UUID | str,
    settings_service: Any,
) -> bool:
    """Decode ``api_key`` and populate request context when valid."""
    decoded = decode_api_key(api_key)
    if decoded.user_id and decoded.user_id != str(expected_user_id):
        return False

    if settings_service.auth_settings.CLERK_AUTH_ENABLED:
        context_payload = auth_header_ctx.get() or {}
        if not isinstance(context_payload, dict):
            context_payload = {}
        if decoded.organization_id:
            context_payload = {**context_payload, "org_id": decoded.organization_id}
        if decoded.user_id:
            context_payload.setdefault("uuid", decoded.user_id)
        if context_payload:
            auth_header_ctx.set(context_payload)

    return True
