"""SSO plugin tables.

These tables are used by the SSO plugin for identity and provider configuration.
Migrations are managed by Langflow (OSS); the plugin must not create or
migrate these tables.

Plugins must use these tables via the models exported from
``langflow.services.database.models`` (e.g. ``SSOUserProfile``, ``SSOConfig``).
"""

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy import Column, ForeignKey, Index
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class SSOUserProfile(SQLModel, table=True):  # type: ignore[call-arg]
    """SSO profile per user. Used by the SSO plugin for JIT provisioning and login."""

    __tablename__ = "sso_user_profile"
    # Use Index(unique=True) to match migration (create_index); avoids model/DB mismatch.
    __table_args__ = (Index("uq_sso_user_profile_provider_user", "sso_provider", "sso_user_id", unique=True),)

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    user_id: UUIDstr = Field(
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        )
    )
    sso_provider: str = Field()
    sso_user_id: str = Field()
    email: str | None = Field(default=None, index=True)
    sso_last_login_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SSOConfig(SQLModel, table=True):  # type: ignore[call-arg]
    """SSO provider configuration (persisted in DB). Used by the SSO plugin."""

    __tablename__ = "sso_config"

    id: UUIDstr = Field(default_factory=uuid4, primary_key=True)
    provider: str = Field(description="oidc, saml, ldap")
    provider_name: str = Field()
    enabled: bool = Field(default=True)
    enforce_sso: bool = Field(default=False)
    client_id: str | None = Field(default=None)
    client_secret_encrypted: str | None = Field(default=None)
    discovery_url: str | None = Field(default=None)
    redirect_uri: str | None = Field(default=None)
    scopes: str | None = Field(default="openid email profile")
    email_claim: str = Field(default="email")
    username_claim: str = Field(default="preferred_username")
    user_id_claim: str = Field(default="sub")
    token_endpoint: str | None = Field(default=None)
    authorization_endpoint: str | None = Field(default=None)
    jwks_uri: str | None = Field(default=None)
    issuer: str | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: UUIDstr | None = Field(
        default=None,
        sa_column=Column(
            sa.Uuid(),
            ForeignKey("user.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
