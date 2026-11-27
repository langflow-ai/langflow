import math

import httpx
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from lfx.utils.secrets import secret_value_to_str

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


def _parse_model_entry(model: object) -> dict | None:
    """Validate a raw model entry from /v1/models and normalize its fields."""
    if not isinstance(model, dict):
        msg = "Malformed model entry in Straitly /models response"
        raise TypeError(msg)
    model_id = model.get("id")
    if model_id is None or model_id == "":
        return None
    if not isinstance(model_id, str):
        msg = f"Invalid model id type: {type(model_id).__name__}"
        raise TypeError(msg)
    if not _supports_text_output(model):
        return None

    raw_name = model.get("name")
    if raw_name is not None and not isinstance(raw_name, str):
        msg = f"Invalid model name type for {model_id}: {type(raw_name).__name__}"
        raise TypeError(msg)
    name = raw_name or model_id

    raw_context = model.get("context_length")
    if raw_context is None:
        context: int | float = 0
    elif (
        isinstance(raw_context, bool)
        or not isinstance(raw_context, (int, float))
        or not math.isfinite(raw_context)
        or raw_context < 0
    ):
        msg = f"Invalid context_length for {model_id}: {raw_context!r}"
        raise ValueError(msg)
    else:
        context = raw_context

    return {"id": model_id, "name": name, "context": context}


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
        key = secret_value_to_str(self.api_key, strip=True)
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
            if not isinstance(payload, dict):
                msg = "Straitly /models response must be a JSON object"
                raise TypeError(msg)
            models = payload.get("data", [])
            if not isinstance(models, list):
                msg = "Straitly /models response 'data' must be a list"
                raise TypeError(msg)
            parsed = []
            for raw_model in models:
                entry = _parse_model_entry(raw_model)
                if entry is not None:
                    parsed.append(entry)
            return sorted(parsed, key=lambda x: x["id"])
        except (httpx.RequestError, httpx.HTTPStatusError, TypeError, ValueError) as e:
            self.log(f"Error fetching Straitly models: {_redact(str(e), key)}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            try:
                options = [m["id"] for m in models]
                tooltips = {
                    m["id"]: f"{m['name']} ({m['context']:,} tokens)" if m["context"] else m["name"] for m in models
                }
            except (KeyError, TypeError, ValueError) as e:
                key = secret_value_to_str(self.api_key, strip=True) or ""
                self.log(f"Error formatting Straitly models: {_redact(str(e), key)}")
                build_config["model_name"]["info"] = f"{MODELS_LOAD_FAILED}. Check your API key and refresh."
                return build_config
            build_config["model_name"]["options"] = options
            build_config["model_name"]["tooltips"] = tooltips
            build_config["model_name"]["info"] = ""
        elif secret_value_to_str(self.api_key, strip=True):
            # Keep the selected model and existing options; report the failure on the field instead.
            build_config["model_name"]["info"] = f"{MODELS_LOAD_FAILED}. Check your API key and refresh."
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Straitly language model."""
        api_key = secret_value_to_str(self.api_key, strip=True)
        if not api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name in {"Loading...", MODELS_LOAD_FAILED}:
            msg = "Please select a model"
            raise ValueError(msg)

        try:
            from langchain_openai import ChatOpenAI
        except ImportError as e:
            msg = 'langchain-openai is required for Straitly. Install it with `uv pip install "lfx-bundles[straitly]"`.'
            raise ImportError(msg) from e

        kwargs = {
            "model": self.model_name,
            "openai_api_key": api_key,
            "openai_api_base": STRAITLY_API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
