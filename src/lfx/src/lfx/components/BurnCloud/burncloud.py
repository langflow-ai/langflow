from __future__ import annotations

from typing import TYPE_CHECKING, Any

import httpx
from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, MessageTextInput, SecretStrInput, SliderInput

LanguageModel = Any
if TYPE_CHECKING:  # pragma: no cover - import only for static analysis
    from lfx.field_typing import LanguageModel as _LanguageModel

    LanguageModel = _LanguageModel

DEFAULT_BURNCLOUD_BASE_URL = "https://ai.burncloud.com"
DEFAULT_BURNCLOUD_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "deepseek-v3",
    "deepseek-r1",
    "gemini-2.5-pro",
    "o3",
    "o4-mini",
    "qwen3-235b-a22b",
    "qwen3-235b-a22b-instruct-2507",
    "llama-4-maverick",
    "gemini-2.5-flash",
    "gemini-2.5-flash-nothink",
    "claude-sonnet-4-20250514",
    "claude-opus-4-20250514",
    "doubao-1.5-pro-256k",
    "grok-4",
]
REQUEST_TIMEOUT_SECONDS = 10.0


class BurnCloudModel(LCModelComponent):
    display_name = "BurnCloud"
    description = "Generate text using BurnCloud's OpenAI-compatible API gateway."
    icon = "BurnCloud"
    name = "BurnCloudModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="BurnCloud API Key",
            info="Your BurnCloud API key for authentication.",
            required=True,
            real_time_refresh=True,
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL",
            info="Override the BurnCloud API base URL if you use a private deployment.",
            value=DEFAULT_BURNCLOUD_BASE_URL,
            advanced=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Select one of the available BurnCloud-hosted models.",
            options=DEFAULT_BURNCLOUD_MODELS,
            value=DEFAULT_BURNCLOUD_MODELS[0],
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            info="Controls randomness. Lower values make outputs more deterministic.",
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        SliderInput(
            name="top_p",
            display_name="Top P",
            value=1.0,
            info="Alternative sampling parameter that limits the probability mass of candidate tokens.",
            range_spec=RangeSpec(min=0, max=1, step=0.01),
            advanced=True,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Output Tokens",
            info="The maximum number of tokens to generate in the response.",
            advanced=True,
        ),
    ]

    def _build_api_base(self) -> str:
        base = (self.base_url or DEFAULT_BURNCLOUD_BASE_URL).rstrip("/")
        if not base.endswith("/v1"):
            base = f"{base}/v1"
        return base

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def get_models(self) -> list[str]:
        if not self.api_key:
            return DEFAULT_BURNCLOUD_MODELS.copy()

        try:
            with httpx.Client(timeout=REQUEST_TIMEOUT_SECONDS) as client:
                response = client.get(
                    f"{self._build_api_base()}/models",
                    headers=self._build_headers(),
                )
            response.raise_for_status()
            payload = response.json()
            models = [item["id"] for item in payload.get("data", []) if item.get("id")]
            return models or DEFAULT_BURNCLOUD_MODELS.copy()
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            self.log(f"Error fetching BurnCloud models: {exc}", "warning")
            return DEFAULT_BURNCLOUD_MODELS.copy()

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None):
        if field_name in {"api_key", "base_url", "model_name"} and field_value:
            model_options = self.get_models()
            build_config.setdefault("model_name", {})
            build_config["model_name"]["options"] = model_options
            if model_options:
                build_config["model_name"].setdefault("value", model_options[0])
        return build_config

    def build_model(self) -> LanguageModel:
        if not self.api_key:
            msg = "BurnCloud API key is required."
            raise ValueError(msg)
        if not self.model_name:
            msg = "Select a BurnCloud model before running the component."
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": self._build_api_base(),
            "temperature": self.temperature if self.temperature is not None else 0.7,
            "top_p": self.top_p if self.top_p is not None else 1.0,
            "streaming": self.stream,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
