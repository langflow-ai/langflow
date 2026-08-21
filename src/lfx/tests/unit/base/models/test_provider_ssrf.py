"""Unit coverage for the shared model-provider base-URL SSRF helpers."""

import pytest
from lfx.base.models.provider_ssrf import openai_compatible_client_kwargs, validate_provider_base_url
from lfx.utils.ssrf_transport import SSRFProtectedSyncTransport, SSRFProtectedTransport

BLOCKED_URLS = [
    "http://169.254.169.254/latest/meta-data",
    "http://10.0.0.5:8000/v1",
    "http://192.168.1.10/v1",
    "http://172.16.0.9/v1",
    "http://[fd00::1]/v1",
    "http://localhost:1234/v1",
    "http://127.0.0.1:1234/v1",
    "http://127.1:1234/v1",
    "http://2130706433:1234/v1",
    "http://[::1]:1234/v1",
]

DEFAULT_URL = "https://api.example-provider.com/v1"


class TestValidateProviderBaseUrl:
    @pytest.mark.parametrize("blocked_url", BLOCKED_URLS)
    def test_should_block_internal_hosts(self, blocked_url):
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_provider_base_url(blocked_url)

    @pytest.mark.parametrize("empty", [None, ""])
    def test_should_no_op_for_empty_url(self, empty):
        assert validate_provider_base_url(empty) is None

    def test_should_no_op_for_provider_default(self):
        """The provider default is server-chosen, so it never needs resolving."""
        assert validate_provider_base_url(DEFAULT_URL, default_url=DEFAULT_URL) is None

    def test_should_ignore_trailing_slash_when_matching_the_default(self):
        assert validate_provider_base_url(DEFAULT_URL + "/", default_url=DEFAULT_URL) is None

    def test_should_still_validate_a_non_default_url(self):
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_provider_base_url("http://169.254.169.254/v1", default_url=DEFAULT_URL)

    def test_should_reject_non_http_scheme(self):
        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_provider_base_url("file:///etc/passwd")

    def test_should_respect_global_kill_switch(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
        assert validate_provider_base_url("http://10.0.0.5:8000/v1") is None

    def test_should_honor_the_operator_allowlist(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "10.0.0.5")
        assert validate_provider_base_url("http://10.0.0.5:8000/v1") is None

    def test_should_not_inherit_the_connector_loopback_exemption(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_CONNECTOR_SSRF_ALLOW_LOOPBACK", "true")

        with pytest.raises(ValueError, match="SSRF Protection"):
            validate_provider_base_url("http://127.0.0.1:1234/v1")

    def test_should_allow_explicitly_allowlisted_loopback(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

        assert validate_provider_base_url("http://127.0.0.1:1234/v1") is None


class TestOpenAICompatibleClientKwargs:
    @pytest.mark.parametrize("blocked_url", BLOCKED_URLS)
    def test_should_block_internal_hosts(self, blocked_url):
        with pytest.raises(ValueError, match="SSRF Protection"):
            openai_compatible_client_kwargs(blocked_url)

    @pytest.mark.parametrize("empty", [None, ""])
    def test_should_return_empty_kwargs_for_empty_url(self, empty):
        assert openai_compatible_client_kwargs(empty) == {}

    def test_should_return_empty_kwargs_for_provider_default(self):
        assert openai_compatible_client_kwargs(DEFAULT_URL, default_url=DEFAULT_URL) == {}

    def test_should_return_pinned_clients_for_allowed_custom_url(self, monkeypatch):
        monkeypatch.setattr("lfx.utils.ssrf_protection.resolve_hostname", lambda _hostname: ["93.184.216.34"])

        kwargs = openai_compatible_client_kwargs("https://provider.example/v1")

        assert set(kwargs) == {"http_client", "http_async_client"}
        assert kwargs["http_client"].follow_redirects is False
        assert kwargs["http_async_client"].follow_redirects is False
        assert isinstance(kwargs["http_client"]._transport, SSRFProtectedSyncTransport)
        assert isinstance(kwargs["http_async_client"]._transport, SSRFProtectedTransport)
        assert kwargs["http_client"]._transport.pinned_ips == {"provider.example": ["93.184.216.34"]}
        assert kwargs["http_async_client"]._transport.pinned_ips == {"provider.example": ["93.184.216.34"]}

    def test_should_return_empty_kwargs_when_protection_is_disabled(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
        assert openai_compatible_client_kwargs("http://10.0.0.5:8000/v1") == {}

    def test_should_allow_explicitly_allowlisted_loopback(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "127.0.0.1")

        kwargs = openai_compatible_client_kwargs("http://127.0.0.1:1234/v1")

        assert set(kwargs) == {"http_client", "http_async_client"}
