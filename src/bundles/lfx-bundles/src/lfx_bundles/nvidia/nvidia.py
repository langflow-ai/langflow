from typing import Any

from lfx.base.models.model import LCModelComponent
from lfx.base.models.provider_ssrf import ensure_credential_endpoint_allowed
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput
from lfx.log.logger import logger
from lfx.schema.dotdict import dotdict
from lfx.utils.ssrf_requests import refuse_redirects

NVIDIA_DEFAULT_BASE_URL = "https://integrate.api.nvidia.com/v1"


# ChatNVIDIA talks to the endpoint through its own ``requests.Session``, which follows
# redirects by default, so -- unlike every other guarded provider here -- there is no
# http_client kwarg to hand it a redirect-free transport. ``requests`` drops the
# Authorization header only when a redirect crosses to a different *hostname*: a same-host
# redirect that changes port or downgrades to http keeps the API key, which would send the
# credential to a service the endpoint guard below never checked. Block redirects on the
# session the client builds instead.
def _block_redirects(model: Any) -> None:
    """Stop the NVIDIA SDK's session from following redirects, on every client it holds.

    The session factory lives on a private attribute of the pinned SDK, so a future release
    may move it. That is a reachable fail-open, so it is logged rather than swallowed; the
    endpoint guard and the SSRF denylist still apply to the initial request either way.
    """
    clients = [getattr(model, attr, None) for attr in ("_client", "_async_client")]
    hardened = False
    for client in clients:
        factory = getattr(client, "get_session_fn", None)
        if not callable(factory):
            continue

        def guarded(*args: Any, _factory=factory, **kwargs: Any):
            return refuse_redirects(_factory(*args, **kwargs))

        client.get_session_fn = guarded
        hardened = True

    if not hardened:
        logger.warning(
            "Could not disable redirect following on the NVIDIA client: "
            "langchain-nvidia-ai-endpoints no longer exposes 'get_session_fn'. "
            "A same-host redirect from the endpoint could forward the API key to an "
            "unvalidated destination."
        )


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

        model = ChatNVIDIA(base_url=self.base_url, api_key=self.api_key or None)
        _block_redirects(model)
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
        model = ChatNVIDIA(
            max_tokens=max_tokens or None,
            model=model_name,
            base_url=self.base_url,
            api_key=api_key,
            temperature=temperature or 0.1,
            seed=seed,
        )
        _block_redirects(model)
        return model
