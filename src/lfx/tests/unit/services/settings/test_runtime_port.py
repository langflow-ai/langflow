"""Tests for runtime_port validator in Settings.

Kubernetes auto-creates service discovery env vars like
LANGFLOW_RUNTIME_PORT=tcp://<ip>:<port> which collide with
pydantic-settings LANGFLOW_ prefix. The validator should
extract the port from URL-like values.
"""

from lfx.services.settings.base import Settings


def test_runtime_port_from_k8s_tcp_url(monkeypatch):
    """Kubernetes tcp:// service discovery value is parsed to the port number."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "tcp://10.96.0.1:7865")
    settings = Settings()
    assert settings.runtime_port == 7865


def test_runtime_port_from_k8s_tcp_url_different_port(monkeypatch):
    """Different port numbers are parsed correctly."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "tcp://10.0.0.5:8080")
    settings = Settings()
    assert settings.runtime_port == 8080


def test_runtime_port_from_integer_string(monkeypatch):
    """A plain integer string is parsed normally."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "7865")
    settings = Settings()
    assert settings.runtime_port == 7865


def test_runtime_port_default_is_none(monkeypatch):
    """Without env var, runtime_port defaults to None."""
    monkeypatch.delenv("LANGFLOW_RUNTIME_PORT", raising=False)
    settings = Settings()
    assert settings.runtime_port is None


def test_runtime_port_garbage_value_returns_none(monkeypatch):
    """Unparseable values fall back to None."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "not-a-port")
    settings = Settings()
    assert settings.runtime_port is None


def test_runtime_port_from_http_url(monkeypatch):
    """http:// URLs are also parsed correctly (validator is scheme-agnostic)."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "http://10.96.0.1:7865")
    settings = Settings()
    assert settings.runtime_port == 7865


def test_runtime_port_url_without_port_returns_none(monkeypatch):
    """A URL without a port component falls back to None."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "tcp://10.96.0.1")
    settings = Settings()
    assert settings.runtime_port is None


def test_runtime_port_url_with_out_of_range_port_returns_none(monkeypatch):
    """A URL with port > 65535 should not crash, falls back to None."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "tcp://10.0.0.1:99999")
    settings = Settings()
    assert settings.runtime_port is None


def test_runtime_port_url_with_non_numeric_port_returns_none(monkeypatch):
    """A URL with non-numeric port should not crash, falls back to None."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "tcp://10.0.0.1:abc")
    settings = Settings()
    assert settings.runtime_port is None


def test_runtime_port_url_with_negative_port_returns_none(monkeypatch):
    """A URL with negative port should not crash, falls back to None."""
    monkeypatch.setenv("LANGFLOW_RUNTIME_PORT", "tcp://10.0.0.1:-1")
    settings = Settings()
    assert settings.runtime_port is None
