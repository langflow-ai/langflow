"""Unit coverage for the shared model-provider base-URL SSRF helpers."""

import pytest
from lfx.base.models.provider_ssrf import (
    ensure_credential_endpoint_allowed,
    is_env_sourced_credential,
    openai_compatible_client_kwargs,
    validate_provider_base_url,
)
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


class TestEnsureCredentialEndpointAllowed:
    """Credential-egress guard for environment-provisioned keys (H1-4000668 / LE-2670).

    An operator's environment-provisioned key must not leave the deployment to a
    tenant-chosen endpoint.
    """

    OPERATOR_KEY = "sk-operator-canary-a1b2c3d4e5"  # pragma: allowlist secret
    CUSTOM_URL = "https://attacker.example.com/v1"

    @pytest.fixture(autouse=True)
    def _operator_key_in_env(self, monkeypatch):
        monkeypatch.setenv("SOME_PROVIDER_API_KEY", self.OPERATOR_KEY)
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)

    def test_should_block_env_sourced_key_to_custom_public_host(self):
        with pytest.raises(ValueError, match="server-provisioned API credential"):
            ensure_credential_endpoint_allowed(self.OPERATOR_KEY, self.CUSTOM_URL, default_url=DEFAULT_URL)

    def test_should_allow_env_sourced_key_to_provider_default(self):
        assert ensure_credential_endpoint_allowed(self.OPERATOR_KEY, DEFAULT_URL, default_url=DEFAULT_URL) is None

    @pytest.mark.parametrize("empty", [None, ""])
    def test_should_allow_env_sourced_key_when_no_custom_url(self, empty):
        assert ensure_credential_endpoint_allowed(self.OPERATOR_KEY, empty, default_url=DEFAULT_URL) is None

    def test_should_allow_tenant_owned_key_to_custom_host(self):
        """A key that exists nowhere in the server environment is the tenant's own."""
        assert (
            ensure_credential_endpoint_allowed("sk-tenant-owned-9z8y7x6w5v", self.CUSTOM_URL, default_url=DEFAULT_URL)
            is None
        )

    def test_should_allow_custom_host_when_operator_allowlists_it(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "attacker.example.com")

        assert ensure_credential_endpoint_allowed(self.OPERATOR_KEY, self.CUSTOM_URL, default_url=DEFAULT_URL) is None

    def test_should_allow_wildcard_allowlist_entry(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "*.example.com")

        assert ensure_credential_endpoint_allowed(self.OPERATOR_KEY, self.CUSTOM_URL, default_url=DEFAULT_URL) is None

    def test_should_not_allow_unrelated_allowlist_entry(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "other.example.com")

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            ensure_credential_endpoint_allowed(self.OPERATOR_KEY, self.CUSTOM_URL, default_url=DEFAULT_URL)

    def test_should_match_secret_wrappers(self):
        from pydantic import SecretStr

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            ensure_credential_endpoint_allowed(SecretStr(self.OPERATOR_KEY), self.CUSTOM_URL, default_url=DEFAULT_URL)

    def test_should_ignore_short_env_values(self, monkeypatch):
        """Low-entropy environment values must not fail closed on coincidental matches."""
        monkeypatch.setenv("SHORT_FLAG", "on")
        assert ensure_credential_endpoint_allowed("on", self.CUSTOM_URL, default_url=DEFAULT_URL) is None

    @pytest.mark.parametrize("empty", [None, ""])
    def test_should_no_op_without_a_key(self, empty):
        assert ensure_credential_endpoint_allowed(empty, self.CUSTOM_URL, default_url=DEFAULT_URL) is None


class TestIsEnvSourcedCredential:
    def test_should_match_an_env_value(self, monkeypatch):
        monkeypatch.setenv("CANARY_CREDENTIAL", "canary-value-0123456789")
        assert is_env_sourced_credential("canary-value-0123456789") is True

    def test_should_not_match_a_value_absent_from_env(self):
        assert is_env_sourced_credential("definitely-not-in-the-environment-xyz") is False

    def test_should_not_match_short_values(self, monkeypatch):
        monkeypatch.setenv("SHORT_ENV", "abc")
        assert is_env_sourced_credential("abc") is False
