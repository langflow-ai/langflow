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
            msg = "URL must start with http:// or https://"
            raise ValueError(msg)
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


class SSOConfig(BaseModel):
    """Complete SSO configuration container."""

    provider: AuthProvider = Field(..., description="Authentication provider type")
    enabled: bool = Field(default=True, description="Whether SSO is enabled")
    enforce_sso: bool = Field(default=False, description="Require SSO for all users (disable password login)")

    # Provider-specific configuration (only one should be set)
    oidc: OIDCConfig | None = Field(default=None, description="OIDC configuration")
    saml: SAMLConfig | None = Field(default=None, description="SAML configuration")
    ldap: LDAPConfig | None = Field(default=None, description="LDAP configuration")

    @field_validator("oidc", "saml", "ldap")
    @classmethod
    def validate_provider_config(cls, v: Any, info) -> Any:
        """Ensure provider-specific config matches the provider type."""
        if v is None:
            return v

        # Get the provider field value
        provider = info.data.get("provider")
        field_name = info.field_name

        # Validate that the config matches the provider
        if provider == AuthProvider.OIDC and field_name != "oidc":
            return None
        if provider == AuthProvider.SAML and field_name != "saml":
            return None
        if provider == AuthProvider.LDAP and field_name != "ldap":
            return None

        return v

    def get_provider_config(self) -> OIDCConfig | SAMLConfig | LDAPConfig:
        """Get the active provider configuration.

        Returns:
            Provider-specific configuration object

        Raises:
            ValueError: If no provider configuration is set
        """
        if self.provider == AuthProvider.OIDC and self.oidc:
            return self.oidc
        if self.provider == AuthProvider.SAML and self.saml:
            return self.saml
        if self.provider == AuthProvider.LDAP and self.ldap:
            return self.ldap

        msg = f"No configuration found for provider: {self.provider}"
        raise ValueError(msg)

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
            msg = f"SSO config file not found: {config_path}"
            raise FileNotFoundError(msg)

        with path.open("r") as f:
            config_data = yaml.safe_load(f)

        if not config_data:
            msg = f"Empty or invalid YAML in config file: {config_path}"
            raise ValueError(msg)

        try:
            return SSOConfig.model_validate(config_data)
        except Exception as e:
            msg = f"Invalid SSO configuration: {e}"
            raise ValueError(msg) from e

    @staticmethod
    def create_example_config(provider: AuthProvider, output_path: str | Path) -> None:
        """Create an example configuration file for a provider.

        Args:
            provider: Authentication provider type
            output_path: Where to write the example config
        """
        path = Path(output_path)

        if provider == AuthProvider.OIDC:
            example = {
                "provider": "oidc",
                "enabled": True,
                "enforce_sso": False,
                "oidc": {
                    "provider_name": "IBM W3ID",
                    "client_id": "your-client-id",
                    "client_secret": "your-client-secret",
                    "discovery_url": "https://w3id.sso.ibm.com/isam/oidc/endpoint/default/.well-known/openid-configuration",
                    "redirect_uri": "https://langflow.example.com/api/v1/auth/callback",
                    "scopes": ["openid", "email", "profile"],
                    "email_claim": "email",
                    "username_claim": "preferred_username",
                    "user_id_claim": "sub",
                },
            }
        elif provider == AuthProvider.SAML:
            example = {
                "provider": "saml",
                "enabled": True,
                "enforce_sso": False,
                "saml": {
                    "provider_name": "Okta",
                    "entity_id": "http://www.okta.com/exk...",
                    "sso_url": "https://example.okta.com/app/example/exk.../sso/saml",
                    "x509_cert": "-----BEGIN CERTIFICATE-----\n...\n-----END CERTIFICATE-----",
                    "sp_entity_id": "https://langflow.example.com",
                    "acs_url": "https://langflow.example.com/api/v1/auth/saml/acs",
                    "email_attribute": "email",
                    "username_attribute": "username",
                    "user_id_attribute": "nameID",
                },
            }
        elif provider == AuthProvider.LDAP:
            example = {
                "provider": "ldap",
                "enabled": True,
                "enforce_sso": False,
                "ldap": {
                    "provider_name": "Active Directory",
                    "server_uri": "ldaps://ad.example.com:636",
                    "bind_dn": "CN=Service Account,OU=Users,DC=example,DC=com",
                    "bind_password": "your-bind-password",
                    "user_search_base": "OU=Users,DC=example,DC=com",
                    "user_search_filter": "(sAMAccountName={username})",
                    "email_attribute": "mail",
                    "username_attribute": "sAMAccountName",
                    "user_id_attribute": "objectGUID",
                    "use_ssl": True,
                },
            }
        else:
            msg = f"Unknown provider: {provider}"
            raise ValueError(msg)

        with path.open("w") as f:
            yaml.dump(example, f, default_flow_style=False, sort_keys=False)
