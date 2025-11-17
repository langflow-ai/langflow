"""Tests for mcp_composer_version validator in Settings."""

from lfx.services.settings.base import Settings


def test_bare_version_gets_tilde_equals_prefix(monkeypatch):
    """Test that a bare version like '0.1.0.7' gets ~= prefix added."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "~=0.1.0.7"


def test_version_with_tilde_equals_is_preserved(monkeypatch):
    """Test that a version with ~= is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "~=0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "~=0.1.0.7"


def test_version_with_greater_than_or_equal_is_preserved(monkeypatch):
    """Test that a version with >= is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", ">=0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == ">=0.1.0.7"


def test_version_with_exact_match_is_preserved(monkeypatch):
    """Test that a version with == is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "==0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "==0.1.0.7"


def test_version_with_less_than_or_equal_is_preserved(monkeypatch):
    """Test that a version with <= is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "<=0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "<=0.1.0.7"


def test_version_with_not_equal_is_preserved(monkeypatch):
    """Test that a version with != is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "!=0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "!=0.1.0.7"


def test_version_with_less_than_is_preserved(monkeypatch):
    """Test that a version with < is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "<0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "<0.1.0.7"


def test_version_with_greater_than_is_preserved(monkeypatch):
    """Test that a version with > is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", ">0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == ">0.1.0.7"


def test_version_with_arbitrary_equality_is_preserved(monkeypatch):
    """Test that a version with === is preserved as-is."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "===0.1.0.7")
    settings = Settings()
    assert settings.mcp_composer_version == "===0.1.0.7"


def test_empty_version_gets_default(monkeypatch):
    """Test that empty string gets default value."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "")
    settings = Settings()
    assert settings.mcp_composer_version == "~=0.1.0.7"


def test_no_env_var_uses_default(monkeypatch):
    """Test that missing env var uses default value."""
    monkeypatch.delenv("LANGFLOW_MCP_COMPOSER_VERSION", raising=False)
    settings = Settings()
    assert settings.mcp_composer_version == "~=0.1.0.7"


def test_three_part_version_gets_prefix(monkeypatch):
    """Test that a 3-part version like '1.2.3' gets ~= prefix."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "1.2.3")
    settings = Settings()
    assert settings.mcp_composer_version == "~=1.2.3"


def test_two_part_version_gets_prefix(monkeypatch):
    """Test that a 2-part version like '1.2' gets ~= prefix."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "1.2")
    settings = Settings()
    assert settings.mcp_composer_version == "~=1.2"


def test_single_digit_version_gets_prefix(monkeypatch):
    """Test that a single digit version like '1' gets ~= prefix."""
    monkeypatch.setenv("LANGFLOW_MCP_COMPOSER_VERSION", "1")
    settings = Settings()
    assert settings.mcp_composer_version == "~=1"


def test_validator_directly():
    """Test calling the validator method directly."""
    # Test bare version
    result = Settings.validate_mcp_composer_version("0.1.0.7")
    assert result == "~=0.1.0.7"

    # Test with specifier
    result = Settings.validate_mcp_composer_version(">=0.1.0.7")
    assert result == ">=0.1.0.7"

    # Test empty
    result = Settings.validate_mcp_composer_version("")
    assert result == "~=0.1.0.7"

    # Test None
    result = Settings.validate_mcp_composer_version(None)
    assert result == "~=0.1.0.7"
