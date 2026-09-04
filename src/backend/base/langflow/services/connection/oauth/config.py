"""Operator-only OAuth registrations; never resolve these settings from a flow."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class OAuthError(ValueError):
    """A deliberately credential-free error safe for API responses."""


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
        uri = urlsplit(self.redirect_uri)
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
            msg = "OAuth redirect must be HTTPS (or loopback HTTP) at the provider callback"
            raise ValueError(msg)
        if self.context == "desktop" and (not loopback or self.client_type != "public"):
            msg = "Desktop OAuth requires a public client and a loopback callback"
            raise ValueError(msg)
        if self.context == "self_managed" and self.owner != "customer":
            msg = "Self-managed OAuth uses customer-owned registrations"
            raise ValueError(msg)
        if self.client_type == "public" and (self.client_secret or self.private_key):
            msg = "Public clients cannot contain registration secrets"
            raise ValueError(msg)
        if self.client_type == "confidential" and bool(self.client_secret) == bool(self.private_key):
            msg = "Confidential clients require exactly one secret or private key"
            raise ValueError(msg)
        if self.private_key and (self.provider != "microsoft" or not self.certificate_thumbprint):
            msg = "Certificate authentication requires Microsoft and a certificate thumbprint"
            raise ValueError(msg)
        if self.private_key and not re.fullmatch(r"[0-9a-fA-F]{64}", self.certificate_thumbprint or ""):
            msg = "Certificate thumbprint must be a SHA-256 digest in hexadecimal"
            raise ValueError(msg)
        if self.profile == "bot" and (self.provider != "slack" or self.client_type == "public"):
            msg = "Only confidential Slack clients support the bot profile"
            raise ValueError(msg)
        if not self.scopes or any(not s or any(c.isspace() or c == "," for c in s) for s in self.scopes):
            msg = "OAuth scopes must be nonempty individual scope names"
            raise ValueError(msg)
        if self.provider == "google" and self.allowed_tenants and not {"openid", "email"} <= set(self.scopes):
            msg = "Google tenant restrictions require openid and email scopes"
            raise ValueError(msg)
        if self.provider == "microsoft":
            if self.allowed_tenants and self.tenant not in self.allowed_tenants:
                msg = "Microsoft authority must belong to the configured tenant restriction"
                raise ValueError(msg)
            # A fixed authority is the tenant restriction, not a browser-supplied hint.
            from uuid import UUID

            try:
                UUID(self.tenant or "")
            except ValueError:
                msg = "Microsoft OAuth requires a fixed tenant UUID"
                raise ValueError(msg) from None
        return self

    def fingerprint(self) -> str:
        # Exclude rotatable secrets, but bind consent and existing grants to their
        # provider, client, tenant, profile, redirect and configured scope ceiling.
        value = self.model_dump(exclude={"client_secret", "private_key", "certificate_thumbprint"})
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class OAuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LANGFLOW_CONNECTION_OAUTH_", extra="ignore", hide_input_in_errors=True
    )
    registrations: SecretStr = SecretStr("{}")
    hosted_enabled: bool = False
    context: Literal["self_managed", "hosted", "desktop"] = "self_managed"

    def registration(self, registration_id: str) -> OAuthRegistration:
        try:
            configs = json.loads(self.registrations.get_secret_value())
            registration = OAuthRegistration.model_validate(configs[registration_id])
        except (ValueError, KeyError, TypeError):
            msg = "OAuth registration is not configured correctly."
            raise OAuthError(msg) from None
        if registration.context != self.context:
            msg = "OAuth registration is unavailable in this deployment context."
            raise OAuthError(msg)
        if registration.owner == "langflow" and registration.context == "hosted" and not self.hosted_enabled:
            msg = "Hosted OAuth registrations are disabled."
            raise OAuthError(msg)
        return registration


def get_oauth_settings() -> OAuthSettings:
    try:
        return OAuthSettings()
    except ValueError:
        msg = "OAuth instance configuration is invalid."
        raise OAuthError(msg) from None
