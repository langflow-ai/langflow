"""Unit coverage for the shared model-provider base-URL SSRF helpers."""

import pytest
from lfx.base.models.provider_ssrf import (
    ensure_credential_endpoint_allowed,
    is_env_sourced_credential,
    openai_compatible_client_kwargs,
    provider_httpx_client_kwargs,
    provider_httpx_clients,
    validate_provider_base_url,
    validate_provider_model_identifier,
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

    def test_should_block_short_env_sourced_keys(self, monkeypatch):
        """A short operator key is still the operator's; failing open would forward it."""
        monkeypatch.setenv("SHORT_PROXY_KEY", "sk-abc")
        with pytest.raises(ValueError, match="server-provisioned API credential"):
            ensure_credential_endpoint_allowed("sk-abc", self.CUSTOM_URL, default_url=DEFAULT_URL)

    def test_should_no_op_for_an_empty_key(self):
        """An empty string is a credential deliberately withheld: the SDK sends no key."""
        assert ensure_credential_endpoint_allowed("", self.CUSTOM_URL, default_url=DEFAULT_URL) is None

    def test_should_no_op_for_a_missing_key_when_no_fallback_is_declared(self):
        """Without a declared SDK fallback there is nothing known to be resolvable."""
        assert ensure_credential_endpoint_allowed(None, self.CUSTOM_URL, default_url=DEFAULT_URL) is None

    # --- host:port allowlist contract (CodeRabbit) ---

    def test_should_allow_matching_host_port_allowlist_entry(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "gateway.example.com:8443")

        assert (
            ensure_credential_endpoint_allowed(
                self.OPERATOR_KEY, "https://gateway.example.com:8443/v1", default_url=DEFAULT_URL
            )
            is None
        )

    def test_should_reject_allowlisted_host_on_a_different_port(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "gateway.example.com:8443")

        with pytest.raises(ValueError, match="server-provisioned API credential"):
            ensure_credential_endpoint_allowed(
                self.OPERATOR_KEY, "https://gateway.example.com:9999/v1", default_url=DEFAULT_URL
            )

    def test_should_allow_any_port_for_a_bare_host_entry(self, monkeypatch):
        """A bare host entry is not port-scoped, so an explicit port still matches."""
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "gateway.example.com")

        assert (
            ensure_credential_endpoint_allowed(
                self.OPERATOR_KEY, "https://gateway.example.com:8443/v1", default_url=DEFAULT_URL
            )
            is None
        )

    # --- cleartext transport (CodeRabbit) ---

    def test_should_reject_cleartext_http_to_an_allowlisted_host(self, monkeypatch):
        """Allowlisting a host sanctions the destination, not sending the key in the clear."""
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "gateway.example.com")

        with pytest.raises(ValueError, match="cleartext"):
            ensure_credential_endpoint_allowed(
                self.OPERATOR_KEY, "http://gateway.example.com/v1", default_url=DEFAULT_URL
            )

    def test_should_allow_cleartext_when_the_operator_opts_in_by_scheme(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "http://gateway.example.com")

        assert (
            ensure_credential_endpoint_allowed(
                self.OPERATOR_KEY, "http://gateway.example.com/v1", default_url=DEFAULT_URL
            )
            is None
        )

    def test_should_still_allow_https_for_a_cleartext_optin_entry(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "http://gateway.example.com")

        assert (
            ensure_credential_endpoint_allowed(
                self.OPERATOR_KEY, "https://gateway.example.com/v1", default_url=DEFAULT_URL
            )
            is None
        )

    def test_should_not_apply_cleartext_rule_to_the_provider_default(self, monkeypatch):
        """LM Studio and LiteLLM Proxy default to http; their own endpoint stays a no-op."""
        monkeypatch.setenv("LOCAL_PROVIDER_KEY", self.OPERATOR_KEY)
        local_default = "http://localhost:1234/v1"

        assert ensure_credential_endpoint_allowed(self.OPERATOR_KEY, local_default, default_url=local_default) is None


class TestEnsureCredentialEndpointAllowedSdkFallback:
    """An absent component key still sends the operator's credential (LE-2670 follow-up).

    ``ChatOpenAI(api_key=None)`` and ``ChatNVIDIA(api_key=None)`` do not send an empty
    Authorization header -- they load the key from the server process environment and send
    that, to whatever base URL the tenant chose. The guard has to judge the credential the
    SDK will resolve, not the one the component happened to pass.
    """

    CUSTOM_URL = "https://attacker.example.com/v1"

    @pytest.fixture(autouse=True)
    def _clean_allowlist(self, monkeypatch):
        monkeypatch.delenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    def test_should_block_absent_key_when_the_sdk_would_resolve_one(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-operator-env-fallback-0123456789")  # pragma: allowlist secret

        with pytest.raises(ValueError, match=r"falls back to \$OPENAI_API_KEY"):
            ensure_credential_endpoint_allowed(
                None, self.CUSTOM_URL, default_url=DEFAULT_URL, sdk_env_fallback="OPENAI_API_KEY"
            )

    def test_should_allow_absent_key_when_the_fallback_var_is_unset(self):
        """Nothing for the SDK to resolve means nothing of the operator's can leave."""
        assert (
            ensure_credential_endpoint_allowed(
                None, self.CUSTOM_URL, default_url=DEFAULT_URL, sdk_env_fallback="OPENAI_API_KEY"
            )
            is None
        )

    def test_should_ignore_a_blank_fallback_var(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "   ")

        assert (
            ensure_credential_endpoint_allowed(
                None, self.CUSTOM_URL, default_url=DEFAULT_URL, sdk_env_fallback="OPENAI_API_KEY"
            )
            is None
        )

    def test_should_allow_absent_key_to_the_provider_default(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-operator-env-fallback-0123456789")  # pragma: allowlist secret

        assert (
            ensure_credential_endpoint_allowed(
                None, DEFAULT_URL, default_url=DEFAULT_URL, sdk_env_fallback="OPENAI_API_KEY"
            )
            is None
        )

    def test_should_allow_absent_key_to_an_allowlisted_host(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-operator-env-fallback-0123456789")  # pragma: allowlist secret
        monkeypatch.setenv("LANGFLOW_PROVIDER_CREDENTIAL_ALLOWED_HOSTS", "attacker.example.com")

        assert (
            ensure_credential_endpoint_allowed(
                None, self.CUSTOM_URL, default_url=DEFAULT_URL, sdk_env_fallback="OPENAI_API_KEY"
            )
            is None
        )

    def test_should_check_the_first_set_variable_of_several(self, monkeypatch):
        monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-operator-0123456789")  # pragma: allowlist secret

        with pytest.raises(ValueError, match=r"falls back to \$NVIDIA_API_KEY"):
            ensure_credential_endpoint_allowed(
                None,
                self.CUSTOM_URL,
                default_url=DEFAULT_URL,
                sdk_env_fallback=("OPENAI_API_KEY", "NVIDIA_API_KEY"),
            )


class TestIsEnvSourcedCredential:
    def test_should_match_an_env_value(self, monkeypatch):
        monkeypatch.setenv("CANARY_CREDENTIAL", "canary-value-0123456789")
        assert is_env_sourced_credential("canary-value-0123456789") is True

    def test_should_not_match_a_value_absent_from_env(self):
        assert is_env_sourced_credential("definitely-not-in-the-environment-xyz") is False

    def test_should_match_short_values(self, monkeypatch):
        """No length floor: a short operator-provisioned key is still the operator's."""
        monkeypatch.setenv("SHORT_ENV", "abc")
        assert is_env_sourced_credential("abc") is True

    def test_should_not_match_an_empty_value(self):
        assert is_env_sourced_credential("") is False
        assert is_env_sourced_credential(None) is False


class TestProviderModelIdentifier:
    """Some provider fields called "endpoint" name a model, not an HTTP endpoint.

    Qianfan's ``endpoint`` is appended to the SDK's own API host as
    ``/chat/{endpoint}``, so running it through the base-URL guard rejected every
    legitimate value. These live here rather than beside the component because the
    qianfan stack is not importable in every environment, and a skipped test would
    leave the validator uncovered.
    """

    @pytest.mark.parametrize(
        "value",
        [
            "ernie-3.5-8k-0329",
            "ernie-4.0-8k",
            "completions_pro",
            "ERNIE_Speed",
            "model.v2",
            "a",
            "",
            "   ",
            None,
        ],
    )
    def test_accepts_model_identifiers(self, value):
        validate_provider_model_identifier(value)

    @pytest.mark.parametrize(
        "value",
        [
            "http://169.254.169.254/latest/meta-data/",
            "https://evil.example.com",
            "//evil.example.com/x",
            "../../etc/passwd",
            "a/../../b",
            "chat/completions",
            "model?x=1",
            "model#frag",
            "model with space",
            "model\nX",
            "model\x00",
            "-leading-dash-is-not-an-identifier",
        ],
    )
    def test_rejects_origin_and_path_injection(self, value):
        with pytest.raises(ValueError, match="model identifier"):
            validate_provider_model_identifier(value)

    def test_error_names_the_field(self):
        with pytest.raises(ValueError, match="Invalid endpoint"):
            validate_provider_model_identifier("http://x/", field_name="endpoint")


class TestCredentialedEndpointRequiresHttps:
    """A plaintext provider endpoint leaks the operator's API key (CWE-319).

    This is not an SSRF question: the host can be perfectly public and routable
    and still put the stored credential on the wire in the clear, so a tenant who
    can edit the field can downgrade it off TLS without needing an internal target.

    The SSRF host check runs first, so these patch it out to exercise the scheme
    rule on its own rather than depending on whether a test host resolves.
    """

    DEFAULT = "https://api.mistral.ai/v1"

    @pytest.fixture(autouse=True)
    def _protection_on(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "true")
        monkeypatch.delenv("LANGFLOW_SSRF_ALLOWED_HOSTS", raising=False)
        monkeypatch.setattr(
            "lfx.base.models.provider_ssrf.validate_strict_url_for_ssrf_or_raise",
            lambda _url: None,
        )
        monkeypatch.setattr(
            "lfx.base.models.provider_ssrf.ssrf_protected_strict_openai_clients_for_url",
            lambda _url: {},
        )
        monkeypatch.setattr(
            "lfx.base.models.provider_ssrf.ssrf_protected_strict_httpx_client_kwargs_for_url",
            lambda _url: ({}, {}),
        )

    @pytest.mark.parametrize(
        "url",
        [
            "http://api.groq.com/openai/v1",
            "http://api.aimlapi.com/v1",
            "http://integrate.api.nvidia.com/v1",
            "http://mistral.example.com/v1",
            "HTTP://api.groq.com/openai/v1",
        ],
    )
    def test_public_http_endpoint_is_rejected(self, url):
        with pytest.raises(ValueError, match="must use https"):
            validate_provider_base_url(url, default_url=self.DEFAULT)

    @pytest.mark.parametrize(
        "helper",
        [provider_httpx_clients, provider_httpx_client_kwargs, openai_compatible_client_kwargs],
    )
    def test_every_credentialed_entry_point_rejects_http(self, helper):
        """The guard belongs to the shared helpers, not to one component."""
        with pytest.raises(ValueError, match="must use https"):
            helper("http://api.groq.com/openai/v1", default_url=self.DEFAULT)

    def test_custom_https_endpoint_is_accepted(self):
        validate_provider_base_url("https://mistral.example.com/v1", default_url=self.DEFAULT)

    def test_https_default_endpoint_is_untouched(self):
        validate_provider_base_url(self.DEFAULT, default_url=self.DEFAULT)
        assert provider_httpx_clients(self.DEFAULT, default_url=self.DEFAULT) == {}
        assert provider_httpx_client_kwargs(self.DEFAULT, default_url=self.DEFAULT) == ({}, {})

    def test_operator_allowlisted_host_may_use_http(self, monkeypatch):
        """A plaintext internal gateway is an operator decision, not a tenant one."""
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "internal-llm.corp")
        validate_provider_base_url("http://internal-llm.corp:8000/v1", default_url=self.DEFAULT)

    def test_allowlisting_one_host_does_not_admit_another(self, monkeypatch):
        monkeypatch.setenv("LANGFLOW_SSRF_ALLOWED_HOSTS", "other.corp")
        with pytest.raises(ValueError, match="must use https"):
            validate_provider_base_url("http://internal-llm.corp:8000/v1", default_url=self.DEFAULT)

    def test_disabled_protection_does_not_enforce(self, monkeypatch):
        """The check is part of the SSRF policy, not a separate always-on control."""
        monkeypatch.setenv("LANGFLOW_SSRF_PROTECTION_ENABLED", "false")
        validate_provider_base_url("http://api.groq.com/openai/v1", default_url=self.DEFAULT)
