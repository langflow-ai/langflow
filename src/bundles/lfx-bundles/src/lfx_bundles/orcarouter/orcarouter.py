import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from pydantic.v1 import SecretStr

ORCAROUTER_BASE_URL = "https://api.orcarouter.ai/v1"

# Shown before the user saves an API key or refreshes the live catalog. The
# ``orcarouter/fusion`` entry is OrcaRouter's adaptive router (routes each
# request across providers); the rest are namespaced upstream model ids. The
# authoritative list is fetched live from ``/v1/models``.
ORCAROUTER_SEED_MODELS = [
    "orcarouter/fusion",
    "openai/gpt-5.5",
    "anthropic/claude-opus-4.8",
    "google/gemini-3.5-flash",
]


class OrcaRouterComponent(LCModelComponent):
    """OrcaRouter API component for language models."""

    display_name = "OrcaRouter"
    description = (
        "OrcaRouter provides unified, adaptive access to models from many providers through a single "
        "OpenAI-compatible API. Use the 'orcarouter/fusion' router for automatic per-request routing."
    )
    icon = "OrcaRouter"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(name="api_key", display_name="API Key", required=True),
        DropdownInput(
            name="model_name",
            display_name="Model",
            options=ORCAROUTER_SEED_MODELS,
            value="orcarouter/fusion",
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
        StrInput(name="site_url", display_name="Site URL", advanced=True),
        StrInput(name="app_name", display_name="App Name", advanced=True),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch available models from OrcaRouter.

        The catalog is served from ``/v1/models``. A valid key returns the full
        catalog; the request still succeeds without one, so the dropdown can be
        populated before credentials are saved.
        """
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {SecretStr(self.api_key).get_secret_value()}"
        try:
            response = httpx.get(f"{ORCAROUTER_BASE_URL}/models", headers=headers, timeout=10.0)
            response.raise_for_status()
            models = response.json().get("data", [])
            return sorted(
                [
                    {
                        "id": m["id"],
                        "name": m.get("name", m["id"]),
                        "context": m.get("context_length", 0),
                    }
                    for m in models
                    if m.get("id")
                ],
                key=lambda x: x["name"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            self.log(f"Error fetching models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['name']} ({m['context']:,} tokens)" for m in models}
        else:
            build_config["model_name"]["options"] = ORCAROUTER_SEED_MODELS
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the OrcaRouter model."""
        if not self.api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "openai_api_key": SecretStr(self.api_key).get_secret_value(),
            "openai_api_base": ORCAROUTER_BASE_URL,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        headers = {}
        if self.site_url:
            headers["HTTP-Referer"] = self.site_url
        if self.app_name:
            headers["X-Title"] = self.app_name
        if headers:
            kwargs["default_headers"] = headers

        return ChatOpenAI(**kwargs)
