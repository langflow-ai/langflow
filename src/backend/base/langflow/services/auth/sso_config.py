"""SSO configuration loader and validator.

This module handles loading SSO configuration from YAML files and validating
the configuration for different authentication providers (OIDC, SAML, LDAP).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, field_validator

from langflow.services.auth.factory import AuthProvider


class OIDCConfig(BaseModel):
    """OIDC provider configuration."""

    provider_name: str = Field(..., description="Human-readable provider name (e.g., 'IBM W3ID', 'Okta')")
    client_id: str = Field(..., description="OAuth 2.0 client ID")
    client_secret: str = Field(..., description="OAuth 2.0 client secret")
    discovery_url: str = Field(..., description="OIDC discovery endpoint URL")
    redirect_uri: str = Field(
        ..., description="OAuth callback URL (e.g., https://langflow.example.com/api/v1/auth/callback)"
    )
    scopes: list[str] = Field(default=["openid", "email", "profile"], description="OAuth scopes to request")

    # Claim mapping configuration
    email_claim: str = Field(default="email", description="JWT claim containing user email")
    username_claim: str = Field(default="preferred_username", description="JWT claim containing username")
    user_id_claim: str = Field(default="sub", description="JWT claim containing unique user ID")

    # Optional advanced settings
    token_endpoint: str | None = Field(default=None, description="Override token endpoint (auto-discovered if not set)")
    authorization_endpoint: str | None = Field(default=None, description="Override authorization endpoint")
    jwks_uri: str | None = Field(default=None, description="Override JWKS URI for token validation")
    issuer: str | None = Field(default=None, description="Expected token issuer")

    @field_validator("discovery_url", "redirect_uri")
    @classmethod
    def validate_url(cls, v: str) -> str:
        """Validate that URLs are properly formatted."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class SAMLConfig(BaseModel):
    """SAML 2.0 provider configuration."""

    provider_name: str = Field(..., description="Human-readable provider name")
    entity_id: str = Field(..., description="SAML entity ID")
    sso_url: str = Field(..., description="SAML SSO endpoint URL")
    x509_cert: str = Field(..., description="IdP X.509 certificate (PEM format)")

    # Service Provider (SP) configuration
    sp_entity_id: str = Field(..., description="Langflow SP entity ID")
    acs_url: str = Field(..., description="Assertion Consumer Service URL")

    # Attribute mapping
    email_attribute: str = Field(default="email", description="SAML attribute containing email")
    username_attribute: str = Field(default="username", description="SAML attribute containing username")
    user_id_attribute: str = Field(default="nameID", description="SAML attribute containing unique user ID")

    # Optional settings
    slo_url: str | None = Field(default=None, description="Single Logout URL")
    name_id_format: str = Field(
        default="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress", description="SAML NameID format"
    )


class LDAPConfig(BaseModel):
    """LDAP/Active Directory configuration."""

    provider_name: str = Field(..., description="Human-readable provider name")
    server_uri: str = Field(..., description="LDAP server URI (e.g., ldaps://ad.example.com:636)")
    bind_dn: str = Field(..., description="Bind DN for LDAP connection")
    bind_password: str = Field(..., description="Bind password")

    # Search configuration
    user_search_base: str = Field(..., description="Base DN for user searches")
    user_search_filter: str = Field(default="(sAMAccountName={username})", description="LDAP filter for user lookup")

    # Attribute mapping
    email_attribute: str = Field(default="mail", description="LDAP attribute containing email")
    username_attribute: str = Field(default="sAMAccountName", description="LDAP attribute containing username")
    user_id_attribute: str = Field(default="objectGUID", description="LDAP attribute containing unique user ID")

    # Optional settings
    use_ssl: bool = Field(default=True, description="Use SSL/TLS for connection")
    group_search_base: str | None = Field(default=None, description="Base DN for group searches")
    group_search_filter: str | None = Field(default=None, description="LDAP filter for group lookup")


class SSOProviderConfig(BaseModel):
    """Single SSO provider configuration."""

    id: str = Field(..., description="Unique identifier for this provider (e.g., 'google', 'w3id', 'azure')")
    provider_type: AuthProvider = Field(..., description="Authentication provider type")
    enabled: bool = Field(default=True, description="Whether this provider is enabled")
    
    # Provider-specific configuration (only one should be set based on provider_type)
    oidc: OIDCConfig | None = Field(default=None, description="OIDC configuration")
    saml: SAMLConfig | None = Field(default=None, description="SAML configuration")
    ldap: LDAPConfig | None = Field(default=None, description="LDAP configuration")

    def get_provider_config(self) -> OIDCConfig | SAMLConfig | LDAPConfig:
        """Get the provider-specific configuration.

        Returns:
            Provider-specific configuration object

        Raises:
            ValueError: If no provider configuration is set
        """
        if self.provider_type == AuthProvider.OIDC and self.oidc:
            return self.oidc
        if self.provider_type == AuthProvider.SAML and self.saml:
            return self.saml
        if self.provider_type == AuthProvider.LDAP and self.ldap:
            return self.ldap
        raise ValueError(f"No configuration found for provider: {self.provider_type}")


class SSOConfig(BaseModel):
    """Complete SSO configuration container supporting multiple providers."""

    enabled: bool = Field(default=True, description="Whether SSO is enabled globally")
    enforce_sso: bool = Field(default=False, description="Require SSO for all users (disable password login)")
    
    # Multiple providers support
    providers: list[SSOProviderConfig] = Field(
        default_factory=list,
        description="List of configured SSO providers"
    )

    def get_provider_by_id(self, provider_id: str) -> SSOProviderConfig | None:
        """Get a specific provider configuration by ID.

        Args:
            provider_id: Unique provider identifier

        Returns:
            Provider configuration or None if not found
        """
        for provider in self.providers:
            if provider.id == provider_id and provider.enabled:
                return provider
        return None

    def get_enabled_providers(self) -> list[SSOProviderConfig]:
        """Get all enabled providers.

        Returns:
            List of enabled provider configurations
        """
        return [p for p in self.providers if p.enabled]


class SSOConfigLoader:
    """Loader for SSO configuration from YAML files."""

    @staticmethod
    def load_from_file(config_path: str | Path) -> SSOConfig:
        """Load SSO configuration from a YAML file.

        Args:
            config_path: Path to YAML configuration file

        Returns:
            Validated SSOConfig object

        Raises:
            FileNotFoundError: If config file doesn't exist
            ValueError: If config is invalid
        """
        path = Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"SSO config file not found: {config_path}")

        with path.open("r") as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            raise ValueError(f"Empty or invalid YAML in config file: {config_path}")

        try:
            return SSOConfig.model_validate(config_data)
        except Exception as e:
            raise ValueError(f"Invalid SSO configuration: {e}") from e

    @staticmethod
    def create_example_config(output_path: str | Path, multi_provider: bool = True) -> None:
        """Create an example configuration file with multiple providers.

        Args:
            output_path: Where to write the example config
            multi_provider: If True, creates config with multiple providers; if False, single provider
        """
        path = Path(output_path)

        if multi_provider:
            # Example with multiple OIDC providers
            example = {
                "enabled": True,
                "enforce_sso": False,
                "providers": [
                    {
                        "id": "google",
                        "provider_type": "oidc",
                        "enabled": True,
                        "oidc": {
                            "provider_name": "Google",
                            "client_id": "your-google-client-id.apps.googleusercontent.com",
                            "client_secret": "your-google-client-secret",
                            "discovery_url": "https://accounts.google.com/.well-known/openid-configuration",
                            "redirect_uri": "http://localhost:7860/api/v1/sso/callback",
                            "scopes": ["openid", "email", "profile"],
                            "email_claim": "email",
                            "username_claim": "email",
                            "user_id_claim": "sub",
                        },
                    },
                    {
                        "id": "w3id",
                        "provider_type": "oidc",
                        "enabled": True,
                        "oidc": {
                            "provider_name": "IBM W3ID",
                            "client_id": "your-w3id-client-id",
                            "client_secret": "your-w3id-client-secret",
                            "discovery_url": "https://w3id.sso.ibm.com/isam/oidc/endpoint/default/.well-known/openid-configuration",
                            "redirect_uri": "http://localhost:7860/api/v1/sso/callback",
                            "scopes": ["openid", "email", "profile"],
                            "email_claim": "email",
                            "username_claim": "preferred_username",
                            "user_id_claim": "sub",
                        },
                    },
                    {
                        "id": "azure",
                        "provider_type": "oidc",
                        "enabled": True,
                        "oidc": {
                            "provider_name": "Microsoft",
                            "client_id": "your-azure-client-id",
                            "client_secret": "your-azure-client-secret",
                            "discovery_url": "https://login.microsoftonline.com/YOUR_TENANT_ID/v2.0/.well-known/openid-configuration",
                            "redirect_uri": "http://localhost:7860/api/v1/sso/callback",
                            "scopes": ["openid", "email", "profile"],
                            "email_claim": "email",
                            "username_claim": "preferred_username",
                            "user_id_claim": "sub",
                        },
                    },
                ],
            }
        else:
            # Single provider example (backward compatible)
            example = {
                "enabled": True,
                "enforce_sso": False,
                "providers": [
                    {
                        "id": "google",
                        "provider_type": "oidc",
                        "enabled": True,
                        "oidc": {
                            "provider_name": "Google",
                            "client_id": "your-client-id.apps.googleusercontent.com",
                            "client_secret": "your-client-secret",
                            "discovery_url": "https://accounts.google.com/.well-known/openid-configuration",
                            "redirect_uri": "http://localhost:7860/api/v1/sso/callback",
                            "scopes": ["openid", "email", "profile"],
                            "email_claim": "email",
                            "username_claim": "email",
                            "user_id_claim": "sub",
                        },
                    }
                ],
            }

        with path.open("w") as f:
            yaml.dump(example, f, default_flow_style=False, sort_keys=False)
