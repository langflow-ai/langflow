import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

STRAITLY_API_BASE = "https://api.straitly.ai/v1"
MODELS_LOAD_FAILED = "Failed to load models"


def _redact(text: str, api_key: str) -> str:
    return text.replace(api_key, "***") if api_key else text


def _supports_text_output(model: dict) -> bool:
    architecture = model.get("architecture")
    if isinstance(architecture, dict):
        modalities = architecture.get("output_modalities")
        if isinstance(modalities, list) and modalities:
            return "text" in modalities
    return True


class StraitlyComponent(LCModelComponent):
    """Straitly API component for language models."""

    display_name = "Straitly"
    description = (
        "Straitly is an OpenAI-compatible AI gateway providing access to 100+ models "
        "including Claude, GPT, Gemini, Grok and DeepSeek through one API key."
    )
    documentation = "https://straitly.ai/docs/quickstart"
    icon = "Straitly"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="Straitly API Key",
            required=True,
            info="Your Straitly API key. Create one at https://straitly.ai/signup.",  # pragma: allowlist secret
        ),
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
        """Validate the Straitly API key and fetch available chat models."""
        if not self.api_key:
            return []
        key = SecretStr(self.api_key).get_secret_value().strip()
        if not key:
            return []
        headers = {"Authorization": f"Bearer {key}"}
        try:
            # GET /v1/models is public on Straitly, so verify the API key via /v1/key first.
            key_response = httpx.get(
                f"{STRAITLY_API_BASE}/key",
                headers=headers,
                timeout=10.0,
            )
            key_response.raise_for_status()

            response = httpx.get(
                f"{STRAITLY_API_BASE}/models",
                headers=headers,
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data", []) if isinstance(payload, dict) else []
            if not isinstance(models, list):
                return []
            return sorted(
                [
                    {
                        "id": m["id"],
                        "name": m.get("name") or m["id"],
                        "context": m.get("context_length") or 0,
                    }
                    for m in models
                    if isinstance(m, dict) and m.get("id") and _supports_text_output(m)
                ],
                key=lambda x: x["id"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching Straitly models: {_redact(str(e), key)}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {
                m["id"]: f"{m['name']} ({m['context']:,} tokens)" if m["context"] else m["name"] for m in models
            }
            build_config["model_name"]["info"] = ""
        elif self.api_key and SecretStr(self.api_key).get_secret_value().strip():
            # Keep the selected model and existing options; report the failure on the field instead.
            build_config["model_name"]["info"] = f"{MODELS_LOAD_FAILED}. Check your API key and refresh."
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Straitly language model."""
        if not self.api_key or not SecretStr(self.api_key).get_secret_value().strip():
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name in {"Loading...", MODELS_LOAD_FAILED}:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value().strip(),
            "openai_api_base": STRAITLY_API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
