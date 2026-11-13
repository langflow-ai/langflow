import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

POPNOW_API_BASE = "https://api.popnow.ai/v1"
MODELS_LOAD_FAILED = "Failed to load models"


class PopNowComponent(LCModelComponent):
    """PopNow API component for language models."""

    display_name = "PopNow"
    description = "PopNow provides Claude, GPT, Gemini, DeepSeek, Kimi and other chat models through one API key."
    icon = "PopNow"

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

    def fetch_models(self) -> list[dict]:
        """Fetch available chat models from PopNow."""
        if not self.api_key:
            return []
        try:
            response = httpx.get(
                f"{POPNOW_API_BASE}/models",
                headers={"Authorization": f"Bearer {SecretStr(self.api_key).get_secret_value()}"},
                timeout=10.0,
            )
            response.raise_for_status()
            models = response.json().get("data", [])
            return sorted(
                [
                    {"id": m["id"], "context": m.get("context_length", 0)}
                    for m in models
                    if m.get("id") and m.get("task") == "chat"
                ],
                key=lambda x: x["id"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['context']:,} tokens" for m in models}
            build_config["model_name"]["info"] = ""
        elif self.api_key:
            # Keep the selected model and existing options; report the failure on the field instead.
            build_config["model_name"]["info"] = f"{MODELS_LOAD_FAILED}. Check your API key and refresh."
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the PopNow model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name in {"Loading...", MODELS_LOAD_FAILED}:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": POPNOW_API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
