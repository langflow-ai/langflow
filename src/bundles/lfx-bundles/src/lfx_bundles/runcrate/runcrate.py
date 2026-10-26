import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

RUNCRATE_BASE_URL = "https://api.runcrate.ai/v1"

# Shown before the live list loads, and if it cannot be fetched.
DEFAULT_MODELS = [
    "deepseek-ai/DeepSeek-V4.1-Flash",
    "zai-org/GLM-5.3",
    "zai-org/GLM-5.3-Flash",
    "Qwen/Qwen3.8-Flash",
    "openai/gpt-oss-120b",
]


class RuncrateModelComponent(LCModelComponent):
    """Runcrate language models through its OpenAI-compatible API."""

    display_name = "Runcrate"
    description = "Generate text with open models (DeepSeek, GLM, Qwen, gpt-oss) on Runcrate's OpenAI-compatible API."
    icon = "Runcrate"
    name = "RuncrateModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="Runcrate API Key",
            info="Create a key at https://www.runcrate.ai/dashboard/api-keys?utm_source=langflow&utm_medium=listing&utm_campaign=gpu_pricing",
            value="RUNCRATE_API_KEY",
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=DEFAULT_MODELS,
            value=DEFAULT_MODELS[0],
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
        """Fetch the chat models from Runcrate's public model list."""
        try:
            response = httpx.get(f"{RUNCRATE_BASE_URL}/models", timeout=10.0)
            response.raise_for_status()
            payload = response.json()
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching models: {e}")
            return []
        models = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(models, list):
            self.log("Unexpected model list response; using the default models")
            return []
        chat_models = [
            {"id": m["id"], "name": str(m.get("name") or m["id"]), "context": m["context_length"]}
            for m in models
            if isinstance(m, dict)
            and isinstance(m.get("id"), str)
            and isinstance(m.get("output_modalities"), list)
            and "text" in m["output_modalities"]
            and isinstance(m.get("context_length"), int)
            and m["context_length"] > 0
        ]
        return sorted(chat_models, key=lambda x: x["name"].casefold())

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Refresh the model options from the live list."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['name']} ({m['context']:,} tokens)" for m in models}
        else:
            build_config["model_name"]["options"] = DEFAULT_MODELS
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Runcrate chat model."""
        if not self.api_key:
            msg = "A Runcrate API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": RUNCRATE_BASE_URL,
            "temperature": self.temperature if self.temperature is not None else 0.7,
            "streaming": self.stream,
        }
        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
