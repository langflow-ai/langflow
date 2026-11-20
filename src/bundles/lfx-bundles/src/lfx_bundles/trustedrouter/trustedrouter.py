import math

import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

TRUSTEDROUTER_API_BASE = "https://api.trustedrouter.com/v1"
DEFAULT_MODEL = "trustedrouter/auto"
MODELS_LOAD_FAILED = "Failed to load models"
MAX_CONTEXT_LENGTH = 2**53


def _context_length(value) -> int:
    """Return a model's context length, treating absent, non-finite or out-of-range values as unset (0).

    Non-numeric values still raise ValueError so a malformed payload takes the refresh-failure path.
    """
    if not value:
        return 0
    try:
        number = float(value)
    except OverflowError:
        return 0
    if not math.isfinite(number) or not 0 <= number <= MAX_CONTEXT_LENGTH:
        return 0
    return int(number)


class TrustedRouterComponent(LCModelComponent):
    """TrustedRouter API component for language models."""

    display_name = "TrustedRouter"
    description = "TrustedRouter routes requests to Anthropic, OpenAI, Google and other models through one API key."
    icon = "TrustedRouter"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=[DEFAULT_MODEL],
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

    def fetch_models(self) -> list[dict]:
        """Fetch available text models from TrustedRouter."""
        try:
            response = httpx.get(f"{TRUSTEDROUTER_API_BASE}/models", timeout=10.0)
            response.raise_for_status()
            models = response.json().get("data", [])
            return sorted(
                [
                    {"id": m["id"], "context": _context_length(m.get("context_length"))}
                    for m in models
                    if isinstance(m.get("id"), str)
                    and m["id"]
                    and str((m.get("architecture") or {}).get("modality", "")).endswith("->text")
                ],
                key=lambda x: x["id"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError, TypeError, AttributeError) as e:
            # Network/HTTP errors plus malformed JSON or unexpected payload shapes.
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['context']:,} tokens" for m in models}
            build_config["model_name"]["info"] = ""
        else:
            # Keep the selected model and existing options; report the failure on the field instead.
            build_config["model_name"]["info"] = f"{MODELS_LOAD_FAILED}. Check your connection and refresh."
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the TrustedRouter model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name in {"Loading...", MODELS_LOAD_FAILED}:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": TRUSTEDROUTER_API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
