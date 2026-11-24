"""Validation tests for the URL component's configurable memory-exhaustion bounds.

These settings cap the per-response and per-fetch byte budgets the URL component
enforces (see ``URLComponent._resolve_byte_limits`` and ``_read_bounded_text``).
Bad env values would silently reopen the DoS the caps close, so Pydantic must
reject non-positive values at config load.
"""

import pytest
from lfx.services.settings.base import Settings
from pydantic import ValidationError


def test_url_component_byte_limits_default_to_documented_values():
    """Keep settings defaults aligned with the documented response and fetch caps."""
    settings = Settings()
    assert settings.url_component_max_response_bytes == 10 * 1024 * 1024
    assert settings.url_component_max_total_bytes == 100 * 1024 * 1024


def test_url_component_max_response_bytes_is_configurable_via_env(monkeypatch):
    """Load the per-response byte cap from its deployment environment variable."""
    monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", "2048")
    settings = Settings()
    assert settings.url_component_max_response_bytes == 2048


def test_url_component_max_total_bytes_is_configurable_via_env(monkeypatch):
    """Load the shared fetch budget from its deployment environment variable."""
    monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", "4096")
    settings = Settings()
    assert settings.url_component_max_total_bytes == 4096


def test_url_component_max_response_bytes_rejects_zero(monkeypatch):
    """Reject a zero response limit during settings validation."""
    monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_RESPONSE_BYTES", "0")
    with pytest.raises(ValidationError):
        Settings()


def test_url_component_max_total_bytes_rejects_negative(monkeypatch):
    """Reject a negative fetch budget during settings validation."""
    monkeypatch.setenv("LANGFLOW_URL_COMPONENT_MAX_TOTAL_BYTES", "-1")
    with pytest.raises(ValidationError):
        Settings()
