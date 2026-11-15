import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

HOPBASE_API_BASE = "https://api.hop-base.com/v1"
MODELS_LOAD_FAILED = "Failed to load models"


class HopBaseComponent(LCModelComponent):
    """HopBase API component for language models."""

    display_name = "HopBase"
    description = (
        "HopBase serves Claude, GPT, Gemini, DeepSeek, Qwen, GLM and other models through one OpenAI-compatible API."
    )
    icon = "HopBase"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=[],
            value="",
            refresh_button=True,
            real_time_refresh=True,
            required=True,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.7,
            range_spec=RangeSpec(min=0, max=2, step=0.01),
            advanced=True,
        ),
        IntInput(name="max_tokens", display_name="Max Tokens", advanced=True),
    ]

    def fetch_models(self) -> list[str]:
        """Fetch the models enabled for this API key from HopBase."""
        if not self.api_key:
            return []
        try:
            response = httpx.get(
                f"{HOPBASE_API_BASE}/models",
                headers={"Authorization": f"Bearer {SecretStr(self.api_key).get_secret_value()}"},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(models, list):
                self.log("Error fetching models: unexpected response shape")
                return []
            return sorted({m["id"] for m in models if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]})
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = models
            build_config["model_name"]["info"] = ""
        elif self.api_key:
            # Keep the selected model and existing options; report the failure on the field instead.
            build_config["model_name"]["info"] = f"{MODELS_LOAD_FAILED}. Check your API key and refresh."
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the HopBase model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name in {"Loading...", MODELS_LOAD_FAILED}:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": HOPBASE_API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
