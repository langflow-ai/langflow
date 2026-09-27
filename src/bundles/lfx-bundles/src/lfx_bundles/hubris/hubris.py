import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import BoolInput, DropdownInput, IntInput, SecretStrInput, SliderInput
from pydantic.v1 import SecretStr

HUBRIS_BASE_URL = "https://api.hubris.pw/v1"


class HubrisComponent(LCModelComponent):
    """Hubris API component for language models."""

    display_name = "Hubris"
    description = "Generates text using models served through the Hubris gateway (OpenAI compatible)."
    icon = "Hubris"
    name = "HubrisModel"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="Hubris API Key",
            info="Create one at https://hubris.pw/keys.",
            value="HUBRIS_API_KEY",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Model IDs are `vendor/model` and are resolved exactly, with no aliasing.",
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
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, the model outputs JSON regardless of passing a schema.",
        ),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch the live catalogue.

        The endpoint is public, so the dropdown fills before a key is entered.
        When a key is present it is still sent: a keyed response also carries the
        user's own saved routes, which a public one does not.
        """
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            response = httpx.get(f"{HUBRIS_BASE_URL}/models", headers=headers, timeout=10.0)
            response.raise_for_status()
            models = response.json().get("data", [])
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.log(f"Error fetching models: {e}")
            return []
        return sorted(
            [
                {
                    "id": m["id"],
                    "name": m.get("display_name", m["id"]),
                    "context": m.get("context_window") or 0,
                }
                for m in models
                if m.get("id")
            ],
            key=lambda x: x["name"],
        )

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Refresh the model dropdown from the live catalogue."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {
                m["id"]: f"{m['name']} ({m['context']:,} tokens)" if m["context"] else m["name"] for m in models
            }
        else:
            build_config["model_name"]["options"] = ["Failed to load models"]
            build_config["model_name"]["value"] = "Failed to load models"
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the Hubris model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name or self.model_name == "Failed to load models":
            msg = "Please select a model"
            raise ValueError(msg)

        output = ChatOpenAI(
            model=self.model_name,
            openai_api_key=SecretStr(self.api_key).get_secret_value(),
            openai_api_base=HUBRIS_BASE_URL,
            temperature=self.temperature if self.temperature is not None else 0.7,
            max_tokens=int(self.max_tokens) if self.max_tokens else None,
            streaming=self.stream,
        )

        if self.json_mode:
            output = output.bind(response_format={"type": "json_object"})

        return output
