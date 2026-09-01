import httpx
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from lfx.utils.ssrf_httpx import ssrf_protected_openai_clients_for_url, ssrf_safe_httpx_get
from lfx.utils.ssrf_protection import SSRFProtectionError
from pydantic.v1 import SecretStr
from typing_extensions import override

# Ark only resolves fully versioned model IDs. The console's short names
# (e.g. "doubao-seed-2.1-pro") return InvalidEndpointOrModel.NotFound, and
# "doubao-seed-evolving" is the sole unversioned alias that resolves. Each ID
# below was verified against POST /api/v3/chat/completions on 2026-08-27.
VOLCENGINE_MODELS = [
    "doubao-seed-2-1-pro-260628",
    "doubao-seed-2-1-turbo-260628",
    "doubao-seed-2-0-pro-260215",
    "doubao-seed-2-0-lite-260428",
    "doubao-seed-2-0-mini-260428",
    "doubao-seed-2-0-code-preview-260215",
    "doubao-seed-1-8-251228",
    "doubao-seed-1-6-251015",
    "doubao-seed-1-6-flash-250828",
    "doubao-seed-1-6-vision-250815",
    "doubao-seed-character-260628",
    "doubao-seed-evolving",
]

# GET /models is a dirty superset: it returned 523 entries on 2026-08-27, most of
# them internal or unreleased, and being listed does not imply the model is
# callable — doubao-seed-1-6-thinking-250715 appears there but 404s on chat.
# Filtering by the "doubao-seed-" prefix alone still leaves 72 entries including
# doubao-seed-1-6-flash-dev-test and doubao-seed-2-0-mini-mtp-train-test, so the
# live list is intersected with the verified IDs above and only ever narrows it.
VOLCENGINE_SUPPORTED_MODELS = frozenset(VOLCENGINE_MODELS)


class VolcengineModelComponent(LCModelComponent):
    display_name = "Volcengine Ark"
    description = "Generate text using ByteDance Doubao models on Volcengine Ark."
    icon = "Volcengine"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="Maximum number of tokens to generate. Set to 0 for unlimited.",
            range_spec=RangeSpec(min=0, max=128000),
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            info="Volcengine Ark model to use. IDs need their full version suffix.",
            options=VOLCENGINE_MODELS,
            value=VOLCENGINE_MODELS[0],
            refresh_button=True,
        ),
        StrInput(
            name="api_base",
            display_name="Volcengine Ark API Base",
            advanced=True,
            info="Base URL for API requests. Defaults to https://ark.cn-beijing.volces.com/api/v3",
            value="https://ark.cn-beijing.volces.com/api/v3",
        ),
        SecretStrInput(
            name="api_key",
            display_name="Volcengine Ark API Key",
            info="The Volcengine Ark API Key",
            advanced=False,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in responses",
            value=1.0,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        DropdownInput(
            name="reasoning_effort",
            display_name="Reasoning Effort",
            info=(
                "Depth of thinking. Support is per-model: the Doubao entries take none through max, "
                "where none and minimal both switch thinking off. Leave empty to use the model default."
            ),
            options=["", "none", "minimal", "low", "medium", "high", "xhigh", "max"],
            value="",
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

    def get_models(self) -> list[str]:
        if not self.api_key:
            return VOLCENGINE_MODELS

        url = f"{self.api_base}/models"
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}

        try:
            response = ssrf_safe_httpx_get(url, headers=headers, timeout=10)
            response.raise_for_status()
            model_list = response.json()
            if not isinstance(model_list, dict):
                msg = f"expected a JSON object, got {type(model_list).__name__}"
                raise TypeError(msg)
            data = model_list.get("data") or []
            listed = [model["id"] for model in data if isinstance(model, dict) and "id" in model]
        except SSRFProtectionError as e:
            self.status = f"SSRF Protection: {e}"
            return VOLCENGINE_MODELS
        except httpx.HTTPError as e:
            self.status = f"Error fetching models: {e}"
            return VOLCENGINE_MODELS
        except (TypeError, ValueError) as e:
            # A 200 can still carry unparseable or unexpectedly shaped JSON; keep the
            # picker working instead of letting it break the refresh.
            self.status = f"Unexpected model list payload: {e}"
            return VOLCENGINE_MODELS
        else:
            # Keep the catalogue usable: see VOLCENGINE_SUPPORTED_MODELS above.
            filtered = [m for m in VOLCENGINE_MODELS if m in set(listed) & VOLCENGINE_SUPPORTED_MODELS]
            return filtered or VOLCENGINE_MODELS

    @override
    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"api_key", "api_base", "model_name"}:
            models = self.get_models()
            build_config["model_name"]["options"] = models
        return build_config

    def build_model(self) -> LanguageModel:
        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            msg = "langchain-openai not installed. Please install with `pip install langchain-openai`"
            raise ImportError(msg) from e

        api_key = SecretStr(self.api_key).get_secret_value() if self.api_key else None
        ssrf_client_kwargs = ssrf_protected_openai_clients_for_url(self.api_base)

        # reasoning_effort is a first-class ChatOpenAI field, so pass it directly
        # rather than through model_kwargs (which warns). Ark rejects
        # thinking.type=disabled sent alongside a graded effort, so the effort is
        # the only thinking control exposed here.
        extra_kwargs = {"reasoning_effort": self.reasoning_effort} if self.reasoning_effort else {}

        output = ChatOpenAI(
            model=self.model_name,
            temperature=self.temperature if self.temperature is not None else 0.1,
            max_tokens=self.max_tokens or None,
            model_kwargs=self.model_kwargs or {},
            base_url=self.api_base,
            api_key=api_key,
            streaming=self.stream if hasattr(self, "stream") else False,
            seed=self.seed,
            **extra_kwargs,
            **ssrf_client_kwargs,
        )

        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output

    def _get_exception_message(self, e: Exception):
        """Get message from Volcengine Ark API exception."""
        try:
            from openai import BadRequestError

            if isinstance(e, BadRequestError):
                message = e.body.get("message")
                if message:
                    return message
        except ImportError:
            pass
        return None
