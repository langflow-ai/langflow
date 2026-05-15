"""Tests for database_url validation when supplied via LANGFLOW_DATABASE_URL."""

import pytest
from lfx.services.settings.base import Settings


def test_invalid_database_url_env_raises(monkeypatch):
    """A malformed LANGFLOW_DATABASE_URL is rejected at construction time."""
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", "not-a-valid-url")
    with pytest.raises(ValueError, match="Invalid database_url"):
        Settings()


def test_valid_database_url_env_accepted(monkeypatch, tmp_path):
    """A valid LANGFLOW_DATABASE_URL is used verbatim."""
    url = f"sqlite:///{tmp_path}/test.db"
    monkeypatch.setenv("LANGFLOW_DATABASE_URL", url)
    settings = Settings()
    assert settings.database_url == url
