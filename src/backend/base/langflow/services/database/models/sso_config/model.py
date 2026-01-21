"""SSO configuration database model.

This module defines the database model for storing SSO configuration.
For single-tenant deployments, there will be only one active SSO config.
For multi-tenant deployments (future), each workspace/tenant can have its own config.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import field_validator
from sqlalchemy import JSON, Column, Text
from sqlmodel import Field, SQLModel

from langflow.schema.serialize import UUIDstr


class SSOConfig(SQLModel, table=True):  # type: ignore[call-arg]
    """SSO configuration stored in database.
    
    This table stores the SSO provider configuration including credentials,
    endpoints, and claim mappings. Sensitive fields like client_secret are
    encrypted before storage.
    """
    
    id: UUIDstr = Field(default_factory=uuid4, primary_key=True, unique=True)
    
    # Provider configuration
    provider: str = Field(index=True, description="SSO provider type: oidc, saml, ldap")
    provider_name: str = Field(description="Human-readable provider name (e.g., 'IBM W3ID', 'Okta')")
    enabled: bool = Field(default=True, description="Whether SSO is currently enabled")
    enforce_sso: bool = Field(default=False, description="Require SSO for all users (disable password login)")
    
    # OIDC-specific fields (nullable for SAML/LDAP configs)
    client_id: str | None = Field(default=None, nullable=True, description="OAuth 2.0 client ID")
    client_secret_encrypted: str | None = Field(default=None, nullable=True, description="Encrypted OAuth 2.0 client secret")
    discovery_url: str | None = Field(default=None, nullable=True, description="OIDC discovery endpoint URL")
    redirect_uri: str | None = Field(default=None, nullable=True, description="OAuth callback URL")
    scopes: str | None = Field(default="openid email profile", nullable=True, description="Space-separated OAuth scopes")
    
    # OIDC claim mapping
    email_claim: str = Field(default="email", description="JWT claim containing user email")
    username_claim: str = Field(default="preferred_username", description="JWT claim containing username")
    user_id_claim: str = Field(default="sub", description="JWT claim containing unique user ID")
    
    # OIDC advanced settings (auto-discovered if not set)
    token_endpoint: str | None = Field(default=None, nullable=True)
    authorization_endpoint: str | None = Field(default=None, nullable=True)
    jwks_uri: str | None = Field(default=None, nullable=True)
    issuer: str | None = Field(default=None, nullable=True)
    
    # SAML-specific fields (nullable for OIDC/LDAP configs)
    entity_id: str | None = Field(default=None, nullable=True, description="SAML entity ID")
    sso_url: str | None = Field(default=None, nullable=True, description="SAML SSO endpoint URL")
    x509_cert: str | None = Field(default=None, nullable=True, description="IdP X.509 certificate")
    sp_entity_id: str | None = Field(default=None, nullable=True, description="Service Provider entity ID")
    acs_url: str | None = Field(default=None, nullable=True, description="Assertion Consumer Service URL")
    slo_url: str | None = Field(default=None, nullable=True, description="Single Logout URL")
    name_id_format: str | None = Field(default=None, nullable=True, description="SAML NameID format")
    
    # SAML attribute mapping
    saml_email_attribute: str | None = Field(default="email", nullable=True)
    saml_username_attribute: str | None = Field(default="username", nullable=True)
    saml_user_id_attribute: str | None = Field(default="nameID", nullable=True)
    
    # LDAP-specific fields (nullable for OIDC/SAML configs)
    server_uri: str | None = Field(default=None, nullable=True, description="LDAP server URI")
    bind_dn: str | None = Field(default=None, nullable=True, description="Bind DN for LDAP connection")
    bind_password_encrypted: str | None = Field(default=None, nullable=True, description="Encrypted bind password")
    user_search_base: str | None = Field(default=None, nullable=True, description="Base DN for user searches")
    user_search_filter: str | None = Field(default="(sAMAccountName={username})", nullable=True)
    use_ssl: bool = Field(default=True, description="Use SSL/TLS for LDAP connection")
    group_search_base: str | None = Field(default=None, nullable=True)
    group_search_filter: str | None = Field(default=None, nullable=True)
    
    # LDAP attribute mapping
    ldap_email_attribute: str | None = Field(default="mail", nullable=True)
    ldap_username_attribute: str | None = Field(default="sAMAccountName", nullable=True)
    ldap_user_id_attribute: str | None = Field(default="objectGUID", nullable=True)
    
    # Additional configuration stored as JSON (stored as JSON string)
    extra_config: str | None = Field(default=None, nullable=True, description="JSON string for additional config")
    
    # Metadata
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: UUID | None = Field(default=None, nullable=True, foreign_key="user.id")
    updated_by: UUID | None = Field(default=None, nullable=True, foreign_key="user.id")
    
    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        """Validate that provider is one of the supported types."""
        allowed = {"oidc", "saml", "ldap", "jwt"}
        if v.lower() not in allowed:
            raise ValueError(f"Provider must be one of: {', '.join(allowed)}")
        return v.lower()


class SSOConfigRead(SQLModel):
    """SSO configuration for API responses (excludes sensitive fields)."""
    
    id: UUIDstr
    provider: str
    provider_name: str
    enabled: bool
    enforce_sso: bool
    
    # OIDC fields (non-sensitive)
    client_id: str | None = None
    discovery_url: str | None = None
    redirect_uri: str | None = None
    scopes: str | None = None
    email_claim: str
    username_claim: str
    user_id_claim: str
    
    # SAML fields (non-sensitive)
    entity_id: str | None = None
    sso_url: str | None = None
    sp_entity_id: str | None = None
    acs_url: str | None = None
    
    # LDAP fields (non-sensitive)
    server_uri: str | None = None
    user_search_base: str | None = None
    use_ssl: bool = True
    
    # Metadata
    created_at: datetime
    updated_at: datetime


class SSOConfigUpdate(SQLModel):
    """SSO configuration for updates."""
    
    provider: str | None = None
    provider_name: str | None = None
    enabled: bool | None = None
    enforce_sso: bool | None = None
    
    # OIDC fields
    client_id: str | None = None
    client_secret: str | None = None  # Will be encrypted before storage
    discovery_url: str | None = None
    redirect_uri: str | None = None
    scopes: str | None = None
    email_claim: str | None = None
    username_claim: str | None = None
    user_id_claim: str | None = None
    
    # OIDC advanced
    token_endpoint: str | None = None
    authorization_endpoint: str | None = None
    jwks_uri: str | None = None
    issuer: str | None = None
    
    # SAML fields
    entity_id: str | None = None
    sso_url: str | None = None
    x509_cert: str | None = None
    sp_entity_id: str | None = None
    acs_url: str | None = None
    slo_url: str | None = None
    name_id_format: str | None = None
    saml_email_attribute: str | None = None
    saml_username_attribute: str | None = None
    saml_user_id_attribute: str | None = None
    
    # LDAP fields
    server_uri: str | None = None
    bind_dn: str | None = None
    bind_password: str | None = None  # Will be encrypted before storage
    user_search_base: str | None = None
    user_search_filter: str | None = None
    use_ssl: bool | None = None
    group_search_base: str | None = None
    group_search_filter: str | None = None
    ldap_email_attribute: str | None = None
    ldap_username_attribute: str | None = None
    ldap_user_id_attribute: str | None = None
    
    # Additional config (JSON string)
    extra_config: str | None = None