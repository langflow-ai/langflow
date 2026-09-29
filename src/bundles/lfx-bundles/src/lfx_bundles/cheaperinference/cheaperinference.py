import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from lfx.utils.secrets import secret_value_to_str

CHEAPER_INFERENCE_BASE_URL = "https://api.cheaperinference.com/v1"
DEFAULT_MODEL = "gpt-5.4-mini"
# Shown until the live model list loads. The live list needs an API key.
DEFAULT_MODELS = [DEFAULT_MODEL, "gpt-5.4", "claude-sonnet-5", "gemini-3.1-pro"]


class CheaperInferenceComponent(LCModelComponent):
    """Cheaper Inference API component for language models."""

    display_name = "Cheaper Inference"
    description = (
        "Cheaper Inference is an OpenAI-compatible API for models from many AI labs. "
        "Each model costs 15–60% less than the list price of its lab."  # noqa: RUF001
    )
    icon = "CheaperInference"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True, real_time_refresh=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=DEFAULT_MODELS,
            value=DEFAULT_MODEL,
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

    def fetch_models(self, api_key: str | None) -> list[dict]:
        """Fetch the text models available to this API key."""
        if not api_key:
            return []
        try:
            response = httpx.get(
                f"{CHEAPER_INFERENCE_BASE_URL}/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching models: {e}")
            return []
        models = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            self.log("Unexpected /models response shape")
            return []
        return sorted(
            [
                {"id": m["id"], "context": m.get("context_length") or 0}
                for m in models
                if isinstance(m, dict) and m.get("id") and m.get("type", "text") == "text"
            ],
            key=lambda x: x["id"],
        )

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Update model options."""
        api_key = field_value if field_name == "api_key" else getattr(self, "api_key", None)
        models = self.fetch_models(secret_value_to_str(api_key))
        if models:
            options = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {
                m["id"]: f"{m['id']} ({m['context']:,} tokens)" for m in models if m["context"]
            }
        else:
            options = list(DEFAULT_MODELS)
        build_config["model_name"]["options"] = options
        if build_config["model_name"].get("value") not in options:
            build_config["model_name"]["value"] = DEFAULT_MODEL if DEFAULT_MODEL in options else options[0]
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Cheaper Inference model."""
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
            "openai_api_base": CHEAPER_INFERENCE_BASE_URL,
            "temperature": self.temperature if self.temperature is not None else 0.7,
            "streaming": bool(self.stream),
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
