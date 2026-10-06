import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from lfx.utils.secrets import secret_value_to_str

OPPER_BASE_URL = "https://api.opper.ai/v3/compat"

# Bare model names are pools: Opper routes each request across the providers serving that model.
OPPER_DEFAULT_MODELS = [
    "claude-sonnet-4-6",
    "claude-opus-5",
    "gpt-5.5",
    "gpt-5.4-mini",
    "gemini-3.8-flash",
    "deepseek-v4-pro",
    "kimi-k3",
    "mistral-large-2512",
]


class OpperComponent(LCModelComponent):
    """Opper API component for language models."""

    display_name = "Opper"
    description = "EU-hosted AI gateway with 700+ models from 50+ providers behind one OpenAI-compatible API."
    icon = "Opper"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True, real_time_refresh=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=OPPER_DEFAULT_MODELS,
            value=OPPER_DEFAULT_MODELS[0],
            refresh_button=True,
            real_time_refresh=True,
            combobox=True,
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

    def fetch_models(self, api_key: str | None) -> list[dict]:
        """Fetch the chat models available to an Opper API key."""
        if not api_key:
            return []
        try:
            response = httpx.get(
                f"{OPPER_BASE_URL}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            response.raise_for_status()
            models = response.json().get("data") or []
            return [
                {"id": m["id"], "context": m.get("context_length") or 0}
                for m in models
                if isinstance(m, dict) and m.get("id") and (m.get("opper") or {}).get("type") != "embedding"
            ]
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, AttributeError, TypeError) as e:
            self.status = f"Error fetching models: {e}"
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update model options."""
        api_key = field_value if field_name == "api_key" else self.api_key
        models = self.fetch_models(secret_value_to_str(api_key))
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {
                m["id"]: f"{m['id']} ({m['context']:,} tokens)" for m in models if m["context"]
            }
        else:
            build_config["model_name"]["options"] = list(OPPER_DEFAULT_MODELS)
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Opper model."""
        api_key = secret_value_to_str(self.api_key)
        if not api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": api_key,
            "openai_api_base": OPPER_BASE_URL,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
