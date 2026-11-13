import httpx
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput

from lfx_bundles.fortytwo.chat import ChatFortytwo

BASE_URL = "https://api.fortytwo.network/v1"
HEADERS = {"HTTP-Referer": "https://langflow.org/", "X-Title": "Langflow"}


class FortytwoComponent(LCModelComponent):
    """Language models served by the Fortytwo Chat Completions API."""

    display_name = "Fortytwo"
    description = "Generate responses and use tools with models on Fortytwo."
    icon = "Fortytwo"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True, real_time_refresh=True),
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
        DropdownInput(
            name="reasoning_effort",
            display_name="Reasoning Effort",
            options=["none", "minimal", "low", "medium", "high", "xhigh", "max"],
            value="medium",
            advanced=True,
        ),
    ]

    def fetch_models(self) -> list[str]:
        """Fetch the authenticated catalogue without a hard-coded model list."""
        if not self.api_key:
            return []
        try:
            response = httpx.get(
                f"{BASE_URL}/models",
                headers={**HEADERS, "Authorization": f"Bearer {self.api_key}"},
                timeout=10.0,
                follow_redirects=False,
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(models, list):
                msg = "Invalid model catalogue"
                raise TypeError(msg)
            return sorted({m["id"] for m in models if isinstance(m, dict) and isinstance(m.get("id"), str) and m["id"]})
        except httpx.HTTPStatusError as exc:
            msg = f"Fortytwo model catalogue returned HTTP {exc.response.status_code}. Check your API key and retry."
            raise ValueError(msg) from None
        except httpx.RequestError:
            msg = "Unable to reach the Fortytwo model catalogue. Please retry."
            raise ValueError(msg) from None
        except (ValueError, TypeError):
            msg = "Fortytwo returned an invalid model catalogue. Please retry."
            raise ValueError(msg) from None

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Refresh choices and discard selections no longer in the catalogue."""
        if field_name not in {"api_key", "model_name"}:
            return build_config
        if field_name == "api_key":
            self.api_key = field_value
        model_config = build_config["model_name"]
        previous = model_config.get("value")
        model_config["options"] = []
        model_config["value"] = ""
        models = self.fetch_models()
        model_config["options"] = models
        model_config["value"] = previous if previous in models else next(iter(models), "")
        return build_config

    def build_model(self) -> LanguageModel:
        """Construct the chat client with the selected model and inference options."""
        if not self.api_key:
            msg = "Fortytwo API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please refresh and select a Fortytwo model"
            raise ValueError(msg)
        if self.max_tokens is not None and self.max_tokens < 0:
            msg = "Max Tokens must not be negative"
            raise ValueError(msg)
        return ChatFortytwo(
            model=self.model_name,
            api_key=self.api_key,
            base_url=BASE_URL,
            default_headers=HEADERS,
            temperature=self.temperature,
            max_tokens=self.max_tokens or None,
            reasoning_effort=self.reasoning_effort,
            use_responses_api=False,
        )
