from typing import Any

from lfx.base.models.model import LCModelComponent
from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput
from lfx.schema.dotdict import dotdict
from lfx.utils.ssrf_requests import refuse_aiohttp_redirects, refuse_redirects

NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


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
    """Make every NVIDIA SDK session refuse redirects, before the SDK issues its first request.

    Installed on the ``_NVIDIAClient`` class rather than on a constructed model, because a
    hook applied to the returned object is already too late: ``ChatNVIDIA(base_url=..., ...)``
    resolves ``available_models`` *during* construction whenever no model name is supplied, so
    the ``/v1/models`` discovery request has been sent -- and may have followed a redirect to a
    host the endpoint guard never saw -- before the caller gets the object back.

    Two seams, because the SDK uses two:

    * ``_create_session`` / ``_create_async_session`` are wrapped, so every request issued
      after construction is redirect-refusing. The async one matters on its own: ``_agenerate``
      and ``_astream`` go through ``get_async_session_fn`` (``aiohttp``), which a sync-only
      hook leaves untouched, and an unfollowed-but-unblocked redirect there forwards the
      prompt body to the redirect target.
    * ``__init__`` is wrapped to pass those same wrapped creators as the ``get_session_fn`` /
      ``get_async_session_fn`` field values. The SDK only assigns them on its *last* line, so
      until then the fields hold their plain ``requests.Session`` / ``aiohttp.ClientSession``
      defaults -- which is exactly what constructor-time discovery would have used. Passing
      the bound creators in preserves the SDK's own TLS (``verify_ssl``) and connector setup;
      the only difference from what it assigns later is the redirect refusal.

    Fails closed. These attributes are private to the pinned ``langchain-nvidia-ai-endpoints``,
    so a future release may move them; this raises rather than quietly running a client that
    can follow a redirect with the operator's key attached.
    """
    try:
        from langchain_nvidia_ai_endpoints import _common
    except ImportError as e:
        msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
        raise ImportError(msg) from e

    client_cls = getattr(_common, "_NVIDIAClient", None)
    if client_cls is None or getattr(client_cls, _REDIRECT_POLICY_INSTALLED, False):
        if client_cls is None:
            msg = (
                "Refusing to build an NVIDIA client: langchain-nvidia-ai-endpoints no longer "
                "exposes '_NVIDIAClient', so redirect following cannot be disabled and a "
                "redirect from the endpoint could forward the API key and prompt to an "
                "unvalidated destination."
            )
            raise ValueError(msg)
        return

    original_init = getattr(client_cls, "__init__", None)
    original_create_session = getattr(client_cls, "_create_session", None)
    original_create_async_session = getattr(client_cls, "_create_async_session", None)
    if not all(callable(attr) for attr in (original_init, original_create_session, original_create_async_session)):
        msg = (
            "Refusing to build an NVIDIA client: langchain-nvidia-ai-endpoints no longer "
            "exposes its session factories, so redirect following cannot be disabled and a "
            "redirect from the endpoint could forward the API key and prompt to an "
            "unvalidated destination."
        )
        raise ValueError(msg)

    def create_session(self: Any) -> Any:
        return refuse_redirects(original_create_session(self))

    def create_async_session(self: Any) -> Any:
        return refuse_aiohttp_redirects(original_create_async_session(self))

    def guarded_init(self: Any, **kwargs: Any) -> None:
        # Seed the declared fields the constructor reads before it reaches its own
        # assignment, so constructor-time model discovery cannot follow a redirect.
        kwargs.setdefault("get_session_fn", self._create_session)
        kwargs.setdefault("get_async_session_fn", self._create_async_session)
        original_init(self, **kwargs)

    # The SDK's session factories are private; hardening them is the whole point here.
    client_cls._create_session = create_session  # noqa: SLF001
    client_cls._create_async_session = create_async_session  # noqa: SLF001
    client_cls.__init__ = guarded_init
    setattr(client_cls, _REDIRECT_POLICY_INSTALLED, True)


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
            value=NVIDIA_DEFAULT_BASE_URL,
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
        ensure_credential_endpoint_allowed(
            self.api_key or None,
            self.base_url,
            default_url=NVIDIA_DEFAULT_BASE_URL,
            # An absent key is not an absent credential: ChatNVIDIA reads NVIDIA_API_KEY
            # from the server environment itself and sends it to whatever base URL is set.
            sdk_env_fallback="NVIDIA_API_KEY",
        )
        try:
            from langchain_nvidia_ai_endpoints import ChatNVIDIA
        except ImportError as e:
            msg = "Please install langchain-nvidia-ai-endpoints to use the NVIDIA model."
            raise ImportError(msg) from e

        # Must precede construction: this call is the model-discovery path, and ChatNVIDIA
        # issues the /v1/models request from inside its constructor.
        _install_redirect_policy()
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
            default_url=NVIDIA_DEFAULT_BASE_URL,
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
        _install_redirect_policy()
        return ChatNVIDIA(
            max_tokens=max_tokens or None,
            model=model_name,
            base_url=self.base_url,
            api_key=api_key,
            temperature=temperature or 0.1,
            seed=seed,
        )
