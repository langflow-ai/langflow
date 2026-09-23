"""Operator-only OAuth registrations; never resolve these settings from a flow."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

#: The one reason worth telling apart. ``registration-unavailable`` means this
#: process cannot see a usable registration for a connection - unparsable or
#: absent ``LANGFLOW_CONNECTION_OAUTH_REGISTRATIONS``, a registration that does
#: not validate, one that belongs to another deployment context. The
#: authorization is intact; the process is configured wrong, so a caller that
#: would otherwise disarm the work (a listener holding a trigger) should retry
#: instead. Every other OAuthError describes the authorization itself and does
#: need a human to reconnect.
OAuthErrorReason = Literal["registration-unavailable"]


class OAuthError(ValueError):
    """A deliberately credential-free error safe for API responses."""

    def __init__(self, message: str, *, reason: OAuthErrorReason | None = None) -> None:
        super().__init__(message)
        self.reason: OAuthErrorReason | None = reason


class OAuthRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)

    provider: Literal["google", "microsoft", "slack"]
    profile: Literal["user", "bot"] = "user"
    owner: Literal["customer", "langflow"] = "customer"
    context: Literal["self_managed", "hosted", "desktop"] = "self_managed"
    client_type: Literal["confidential", "public"] = "confidential"
    client_id: str = Field(min_length=1, max_length=512)
    client_secret: SecretStr | None = None
    private_key: SecretStr | None = None
    certificate_thumbprint: str | None = None
    redirect_uri: str
    scopes: list[str] = Field(min_length=1, max_length=512)
    tenant: str | None = None
    allowed_tenants: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_registration(self) -> OAuthRegistration:
        redirect_error = "OAuth redirect must be HTTPS (or loopback HTTP) at the provider callback"
        try:
            uri = urlsplit(self.redirect_uri)
        except ValueError:
            raise OAuthError(redirect_error) from None
        loopback = uri.hostname in {"localhost", "127.0.0.1", "::1"}
        expected_path = f"/api/v1/connections/oauth/{self.provider}/callback"
        if (
            not uri.hostname
            or uri.username
            or uri.password
            or uri.query
            or uri.fragment
            or uri.path != expected_path
            or (uri.scheme != "https" and not (uri.scheme == "http" and loopback))
        ):
            raise OAuthError(redirect_error)
        if self.context == "desktop" and (not loopback or self.client_type != "public"):
            msg = "Desktop OAuth requires a public client and a loopback callback"
            raise OAuthError(msg)
        if self.context == "self_managed" and self.owner != "customer":
            msg = "Self-managed OAuth uses customer-owned registrations"
            raise OAuthError(msg)
        if self.client_type == "public" and (self.client_secret or self.private_key):
            msg = "Public clients cannot contain registration secrets"
            raise OAuthError(msg)
        if self.client_type == "confidential" and bool(self.client_secret) == bool(self.private_key):
            msg = "Confidential clients require exactly one secret or private key"
            raise OAuthError(msg)
        if self.private_key and (self.provider != "microsoft" or not self.certificate_thumbprint):
            msg = "Certificate authentication requires Microsoft and a certificate thumbprint"
            raise OAuthError(msg)
        if self.private_key and not re.fullmatch(r"[0-9a-fA-F]{64}", self.certificate_thumbprint or ""):
            msg = "Certificate thumbprint must be a SHA-256 digest in hexadecimal"
            raise OAuthError(msg)
        if self.profile == "bot" and (self.provider != "slack" or self.client_type == "public"):
            msg = "Only confidential Slack clients support the bot profile"
            raise OAuthError(msg)
        if not self.scopes or any(not s or any(c.isspace() or c == "," for c in s) for s in self.scopes):
            msg = "OAuth scopes must be nonempty individual scope names"
            raise OAuthError(msg)
        if self.provider == "google" and self.allowed_tenants and not {"openid", "email"} <= set(self.scopes):
            msg = "Google tenant restrictions require openid and email scopes"
            raise OAuthError(msg)
        if self.provider == "microsoft":
            if self.allowed_tenants and self.tenant not in self.allowed_tenants:
                msg = "Microsoft authority must belong to the configured tenant restriction"
                raise OAuthError(msg)
            # A fixed authority is the tenant restriction, not a browser-supplied hint.
            from uuid import UUID

            try:
                UUID(self.tenant or "")
            except ValueError:
                msg = "Microsoft OAuth requires a fixed tenant UUID"
                raise OAuthError(msg) from None
        return self

    def fingerprint(self) -> str:
        # Exclude rotatable secrets, but bind consent and existing grants to their
        # provider, client, tenant, profile, redirect and configured scope ceiling.
        value = self.model_dump(exclude={"client_secret", "private_key", "certificate_thumbprint"})
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def _registration_validation_message(error: ValidationError) -> str:
    # Only our explicitly credential-free validator errors can supply text.
    # Pydantic messages, inputs, contexts and unknown field names may hold secrets.
    detail = error.errors(include_input=False, include_url=False)[0]
    cause = detail.get("ctx", {}).get("error")
    if isinstance(cause, OAuthError):
        return str(cause)
    if detail["type"] == "extra_forbidden":
        return "OAuth registration contains unsupported fields."
    location = detail["loc"]
    if location and location[0] in OAuthRegistration.model_fields:
        field = location[0]
        if detail["type"] == "missing":
            return f"OAuth registration field '{field}' is required."
        return f"OAuth registration field '{field}' is invalid."
    return "OAuth registration must be a JSON object."


class OAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANGFLOW_CONNECTION_OAUTH_", extra="ignore", hide_input_in_errors=True
    )
    registrations: SecretStr = SecretStr("{}")
    hosted_enabled: bool = False
    context: Literal["self_managed", "hosted", "desktop"] = "self_managed"

    def registration_ids(self) -> list[str]:
        """Return the configured registration names, without validating them.

        A caller that needs a registration still goes through
        :meth:`registration`, which is where every availability rule lives.
        """
        try:
            configs = json.loads(self.registrations.get_secret_value())
        except ValueError:
            return []
        if not isinstance(configs, dict):
            return []
        return sorted(str(registration_id) for registration_id in configs)

    def registration(self, registration_id: str) -> OAuthRegistration:
        try:
            configs = json.loads(self.registrations.get_secret_value())
        except ValueError:
            msg = "OAuth registrations must contain valid JSON."
            raise OAuthError(msg, reason="registration-unavailable") from None
        if not isinstance(configs, dict):
            msg = "OAuth registrations must be a JSON object keyed by registration ID."
            raise OAuthError(msg, reason="registration-unavailable")
        if registration_id not in configs:
            msg = "OAuth registration ID is not configured."
            raise OAuthError(msg, reason="registration-unavailable")
        try:
            registration = OAuthRegistration.model_validate(configs[registration_id])
        except ValidationError as exc:
            raise OAuthError(_registration_validation_message(exc), reason="registration-unavailable") from None
        except (ValueError, TypeError):
            msg = "OAuth registration is not configured correctly."
            raise OAuthError(msg, reason="registration-unavailable") from None
        if registration.context != self.context:
            msg = "OAuth registration is unavailable in this deployment context."
            raise OAuthError(msg, reason="registration-unavailable")
        if registration.owner == "langflow" and registration.context == "hosted" and not self.hosted_enabled:
            msg = "Hosted OAuth registrations are disabled."
            raise OAuthError(msg, reason="registration-unavailable")
        return registration


def get_oauth_settings() -> OAuthSettings:
    try:
        return OAuthSettings()
    except ValueError:
        msg = "OAuth instance configuration is invalid."
        raise OAuthError(msg, reason="registration-unavailable") from None
