"""Tests for the cors_origins validator's comma-split parsing.

cors_origins is exercised through the LANGFLOW_CORS_ORIGINS env var because
Settings only honors env-sourced values for these fields.
"""

from lfx.services.settings.base import Settings


def test_cors_origins_wildcard_preserved(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CORS_ORIGINS", "*")
    settings = Settings()
    assert settings.cors_origins == "*"


def test_cors_origins_single_value_wrapped_in_list(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CORS_ORIGINS", "https://example.com")
    settings = Settings()
    assert settings.cors_origins == ["https://example.com"]


def test_cors_origins_comma_split(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CORS_ORIGINS", "https://a.com,https://b.com")
    settings = Settings()
    assert settings.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_trailing_comma_filtered(monkeypatch):
    """A trailing comma must not produce an empty-string entry."""
    monkeypatch.setenv("LANGFLOW_CORS_ORIGINS", "https://a.com,https://b.com,")
    settings = Settings()
    assert settings.cors_origins == ["https://a.com", "https://b.com"]
    assert "" not in settings.cors_origins


def test_cors_origins_double_comma_filtered(monkeypatch):
    """Double commas must not produce empty-string entries."""
    monkeypatch.setenv("LANGFLOW_CORS_ORIGINS", "https://a.com,,https://b.com")
    settings = Settings()
    assert settings.cors_origins == ["https://a.com", "https://b.com"]


def test_cors_origins_whitespace_stripped(monkeypatch):
    monkeypatch.setenv("LANGFLOW_CORS_ORIGINS", "  https://a.com  ,  https://b.com  ")
    settings = Settings()
    assert settings.cors_origins == ["https://a.com", "https://b.com"]
