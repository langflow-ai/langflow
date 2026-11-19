from typing import Any

from lfx.base.models.model import LCModelComponent
from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed, validate_provider_base_url
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput
from lfx.schema.dotdict import dotdict
from lfx.utils.ssrf_requests import refuse_aiohttp_redirects, refuse_redirects

DEFAULT_NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"


# ChatNVIDIA talks to the endpoint through transports it owns -- ``requests`` for blocking
# calls, ``aiohttp`` for async inference and streaming -- and both follow redirects by
# default, so there is no ``http_client`` kwarg to hand it a redirect-free transport.
# ``requests`` and ``aiohttp`` drop the Authorization header only when a redirect crosses to
# a different *hostname*: a same-host redirect that changes port or downgrades to http keeps
# the API key, which would send the credential -- and the prompt body -- to a service the
# endpoint guard below never checked. Install a redirect-refusing policy on the SDK's own
# session factories instead.
_REDIRECT_POLICY_INSTALLED = "_lfx_redirect_policy_installed"


def _install_redirect_policy() -> None:
    """Protect both SDK clients before ChatNVIDIA can discover models or send prompts.

    The pinned SDK builds separate sync and async clients. The base class owns the
    requests session factory; the async subclass owns the aiohttp factory. Harden both
    before ChatNVIDIA constructs them, since its sync-client finalization can discover
    models before ChatNVIDIA returns. Seed the session fields before each constructor
    runs as well, preserving the SDK factories' TLS and connector configuration.

    These SDK attributes are private, so validate both clients before changing either
    one and refuse to build if a future SDK moves a required factory.
    """
    try:
        from langchain_nvidia_ai_endpoints import _common
    except ImportError as e:
        msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
        raise ImportError(msg) from e

    client_specs = (
        ("_NVIDIABaseClient", "_create_session", "get_session_fn", refuse_redirects),
        ("_NVIDIAAsyncClient", "_create_async_session", "get_async_session_fn", refuse_aiohttp_redirects),
    )
    clients = []
    for class_name, factory_name, field_name, protect_session in client_specs:
        client_cls = getattr(_common, class_name, None)
        if client_cls is None:
            msg = (
                "Refusing to build an NVIDIA client: langchain-nvidia-ai-endpoints no longer "
                f"exposes '{class_name}', so redirect following cannot be disabled and a "
                "redirect from the endpoint could forward the API key and prompt to an "
                "unvalidated destination."
            )
            raise ValueError(msg)
        if not all(callable(getattr(client_cls, name, None)) for name in ("__init__", factory_name)):
            msg = (
                "Refusing to build an NVIDIA client: langchain-nvidia-ai-endpoints no longer "
                "exposes its session factories, so redirect following cannot be disabled and a "
                "redirect from the endpoint could forward the API key and prompt to an "
                "unvalidated destination."
            )
            raise ValueError(msg)
        clients.append((client_cls, factory_name, field_name, protect_session))

    def install_client_policy(client_cls: Any, factory_name: str, field_name: str, protect_session: Any) -> None:
        # An inherited base-class marker must not skip the async subclass's factory.
        """Wrap each SDK client once with its own redirect protection."""
        if client_cls.__dict__.get(_REDIRECT_POLICY_INSTALLED, False):
            return
        original_init = client_cls.__init__
        original_create_session = getattr(client_cls, factory_name)

        def create_session(self: Any) -> Any:
            """Protect the session returned by the original SDK factory."""
            return protect_session(original_create_session(self))

        def guarded_init(self: Any, **kwargs: Any) -> None:
            """Provide the protected factory before constructor-time model discovery."""
            kwargs.setdefault(field_name, getattr(self, factory_name))
            original_init(self, **kwargs)

        setattr(client_cls, factory_name, create_session)
        client_cls.__init__ = guarded_init
        setattr(client_cls, _REDIRECT_POLICY_INSTALLED, True)

    for client in clients:
        install_client_policy(*client)


class NVIDIAModelComponent(LCModelComponent):
    display_name = "NVIDIA"
    description = "Generates text using NVIDIA LLMs."
    icon = "NVIDIA"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            info="The name of the NVIDIA model to use.",
            advanced=False,
            value=None,
            options=[],
            combobox=True,
            refresh_button=True,
        ),
        BoolInput(
            name="detailed_thinking",
            display_name="Detailed Thinking",
            info="If true, the model will return a detailed thought process. Only supported by reasoning models.",
            value=False,
            show=False,
        ),
        BoolInput(
            name="tool_model_enabled",
            display_name="Enable Tool Models",
            info="If enabled, only show models that support tool-calling.",
            advanced=False,
            value=False,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="NVIDIA Base URL",
            value=DEFAULT_NVIDIA_BASE_URL,
            info="The base URL of the NVIDIA API. Defaults to https://integrate.api.nvidia.com/v1.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="NVIDIA API Key",
            info="The NVIDIA API Key.",
            advanced=False,
            value="NVIDIA_API_KEY",
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            info="Run inference with this temperature.",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
    ]

    def get_models(self, *, tool_model_enabled: bool | None = None) -> list[str]:
        # Note: don't include the previous model, as it may not exist in available models from the new base url
        # The key sent below may resolve to the operator's environment-provisioned
        # credential; refuse to forward it to a tenant-chosen endpoint.
        """List models only after validating credentials and protecting SDK redirects."""
        ensure_credential_endpoint_allowed(
            self.api_key or None,
            self.base_url,
            default_url=DEFAULT_NVIDIA_BASE_URL,
            # An absent key is not an absent credential: ChatNVIDIA reads NVIDIA_API_KEY
            # from the server environment itself and sends it to whatever base URL is set.
            sdk_env_fallback="NVIDIA_API_KEY",
        )
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
            raise ImportError(msg) from e

        # base_url is tenant-editable and the SDK sends the operator's API key to whatever
        # host it names. Block internal/cloud-metadata destinations before connecting.
        # This is the only host check on this path: validate_provider_base_url is the
        # strict one (no literal-loopback exemption, and it requires https for a
        # credential-bearing endpoint), so running validate_connector_url_for_ssrf ahead of
        # it only rejected the same URLs sooner, with a weaker message and a second lookup.
        #
        # Residual: this is validate-then-connect, not connection-time pinning.
        # langchain-nvidia-ai-endpoints 1.5 builds its own requests.Session in
        # _NVIDIABaseClient._create_session, so there is no supported hook to dial a
        # pre-resolved IP while keeping TLS SNI and certificate verification --
        # _install_redirect_policy below wraps that factory, which stops a redirect but does
        # not pin an address. A hostname whose DNS answer changes between this check and the
        # SDK's own resolution is therefore not covered. Literal IPs - the high-value
        # targets, cloud metadata and RFC1918 - have no DNS to rebind and are blocked
        # outright. Deployments that need a hard guarantee should restrict destinations with
        # the ssrf_allowed_hosts operator allowlist.
        validate_provider_base_url(self.base_url, default_url=DEFAULT_NVIDIA_BASE_URL)

        # Must precede construction: this call is the model-discovery path, and ChatNVIDIA
        # issues the /v1/models request from inside its constructor.
        _install_redirect_policy()
        # Note: don't include the previous model, as it may not exist in available models from the new base url
        model = ChatNVIDIA(base_url=self.base_url, api_key=self.api_key or None)
        if tool_model_enabled:
            tool_models = [m for m in model.get_available_models() if m.supports_tools]
            return sorted(m.id for m in tool_models)
        return sorted(m.id for m in model.available_models)

    def update_build_config(self, build_config: dotdict, _field_value: Any, field_name: str | None = None):
        if field_name in {"model_name", "tool_model_enabled", "base_url", "api_key"}:
            try:
                ids = self.get_models(tool_model_enabled=self.tool_model_enabled)
                build_config["model_name"]["options"] = ids

                if "value" not in build_config["model_name"] or build_config["model_name"]["value"] is None:
                    build_config["model_name"]["value"] = ids[0]
                elif build_config["model_name"]["value"] not in ids:
                    build_config["model_name"]["value"] = None

                # TODO: use api to determine if model supports detailed thinking
                if build_config["model_name"]["value"] == "nemotron":
                    build_config["detailed_thinking"]["show"] = True
                else:
                    build_config["detailed_thinking"]["value"] = False
                    build_config["detailed_thinking"]["show"] = False
            except Exception as e:
                msg = f"Error getting model names: {e}"
                build_config["model_name"]["value"] = None
                build_config["model_name"]["options"] = []
                raise ValueError(msg) from e

        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        api_key = self.api_key or None
        ensure_credential_endpoint_allowed(
            api_key,
            self.base_url,
            default_url=DEFAULT_NVIDIA_BASE_URL,
            sdk_env_fallback="NVIDIA_API_KEY",
        )
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
            raise ImportError(msg) from e
        temperature = self.temperature
        model_name: str = self.model_name
        max_tokens = self.max_tokens
        seed = self.seed
        # base_url is tenant-editable and the SDK sends the operator's API key to whatever
        # host it names. Block internal/cloud-metadata destinations before connecting.
        validate_provider_base_url(self.base_url, default_url=DEFAULT_NVIDIA_BASE_URL)
        _install_redirect_policy()
        return ChatNVIDIA(
            max_tokens=max_tokens or None,
            model=model_name,
            base_url=self.base_url,
            api_key=api_key,
            temperature=temperature or 0.1,
            seed=seed,
        )
