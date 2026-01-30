"""Unit tests for SSO configuration loader."""

import tempfile
from pathlib import Path

import pytest
from langflow.services.auth.factory import AuthProvider
from langflow.services.auth.sso_config import OIDCConfig, SSOConfig, SSOConfigLoader

# Test constants
TEST_CLIENT_SECRET = "test-secret"  # noqa: S105
TEST_SECRET = "secret"  # noqa: S105


def test_oidc_config_validation():
    """Test OIDC configuration validation."""
    config = OIDCConfig(
        provider_name="IBM W3ID",
        client_id="test-client-id",
        client_secret=TEST_CLIENT_SECRET,
        discovery_url="https://w3id.sso.ibm.com/isam/oidc/endpoint/default/.well-known/openid-configuration",
        redirect_uri="https://langflow.example.com/api/v1/auth/callback",
    )

    assert config.provider_name == "IBM W3ID"
    assert config.client_id == "test-client-id"
    assert config.scopes == ["openid", "email", "profile"]  # default scopes
    assert config.email_claim == "email"  # default claim


def test_oidc_config_invalid_url():
    """Test that invalid URLs are rejected."""
    with pytest.raises(ValueError, match="URL must start with"):
        OIDCConfig(
            provider_name="Test",
            client_id="test",
            client_secret=TEST_SECRET,
            discovery_url="invalid-url",
            redirect_uri="https://example.com/callback",
        )


def test_sso_config_loader_from_yaml():
    """Test loading SSO config from YAML file."""
    yaml_content = """
provider: oidc
enabled: true
enforce_sso: false
oidc:
  provider_name: IBM W3ID
  client_id: test-client-id
  client_secret: test-secret
  discovery_url: https://w3id.sso.ibm.com/isam/oidc/endpoint/default/.well-known/openid-configuration
  redirect_uri: https://langflow.example.com/api/v1/auth/callback
  scopes:
    - openid
    - email
    - profile
  email_claim: email
  username_claim: preferred_username
  user_id_claim: sub
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        temp_path = f.name

    try:
        config = SSOConfigLoader.load_from_file(temp_path)

        assert config.provider == AuthProvider.OIDC
        assert config.enabled is True
        assert config.enforce_sso is False
        assert config.oidc is not None
        assert config.oidc.provider_name == "IBM W3ID"
        assert config.oidc.client_id == "test-client-id"
        assert (
            config.oidc.discovery_url
            == "https://w3id.sso.ibm.com/isam/oidc/endpoint/default/.well-known/openid-configuration"
        )
    finally:
        Path(temp_path).unlink()


def test_sso_config_loader_file_not_found():
    """Test that FileNotFoundError is raised for missing files."""
    with pytest.raises(FileNotFoundError):
        SSOConfigLoader.load_from_file("/nonexistent/path/config.yaml")


def test_sso_config_get_provider_config():
    """Test getting provider-specific configuration."""
    config = SSOConfig(
        provider=AuthProvider.OIDC,
        enabled=True,
        oidc=OIDCConfig(
            provider_name="Test",
            client_id="test",
            client_secret=TEST_SECRET,
            discovery_url="https://example.com/.well-known/openid-configuration",
            redirect_uri="https://langflow.example.com/callback",
        ),
    )

    provider_config = config.get_provider_config()
    assert isinstance(provider_config, OIDCConfig)
    assert provider_config.provider_name == "Test"


def test_sso_config_create_example_oidc():
    """Test creating example OIDC configuration."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        temp_path = f.name

    try:
        SSOConfigLoader.create_example_config(AuthProvider.OIDC, temp_path)

        # Verify the file was created and can be loaded
        config = SSOConfigLoader.load_from_file(temp_path)
        assert config.provider == AuthProvider.OIDC
        assert config.oidc is not None
        assert config.oidc.provider_name == "IBM W3ID"
    finally:
        Path(temp_path).unlink()
