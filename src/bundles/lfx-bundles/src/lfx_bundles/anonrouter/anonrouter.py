import httpx
from langchain_openai import ChatOpenAI
from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.field_typing.range_spec import RangeSpec
from lfx.inputs.inputs import DropdownInput, IntInput, SecretStrInput, SliderInput
from lfx.utils.secrets import secret_value_to_str

# The single origin an OpenAI-compatible client needs. ``/models`` is served here
# only for an ``ar_`` bearer: without one the origin answers 404, so discovery is
# never attempted unauthenticated.
BASE_URL = "https://api.anonrouter.ai/v1"

# ``model_type`` values that cannot serve a chat completion.
NON_CHAT_MODEL_TYPES = frozenset({"embedding", "image", "tts"})


class AnonRouterComponent(LCModelComponent):
    """AnonRouter API component for language models."""

    display_name = "AnonRouter"
    description = "AnonRouter routes requests to models from many providers through one OpenAI-compatible API."
    icon = "AnonRouter"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="An AnonRouter inference key (prefix 'ar_') with OpenAI-compatible access enabled.",
            required=True,
            real_time_refresh=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Models enabled for your key. Ids keep their creator/model form, e.g. 'meta-llama/llama-3.3-70b'.",
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

    def fetch_models(self, api_key: str | None = None) -> list[dict]:
        """Fetch the chat models enabled for an AnonRouter key.

        ``GET /v1/models`` requires the key: the origin routes it on the bearer and
        answers 404 without one, so an unauthenticated call can only ever fail.
        """
        token = secret_value_to_str(api_key if api_key is not None else getattr(self, "api_key", None), strip=True)
        if not token:
            self.status = "Enter an AnonRouter API key to load the model list."
            return []

        try:
            response = httpx.get(
                f"{BASE_URL}/models",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10.0,
            )
            response.raise_for_status()
            payload = response.json()
            models = payload.get("data", []) if isinstance(payload, dict) else payload
        except (httpx.RequestError, httpx.HTTPStatusError, ValueError) as e:
            self.status = f"Error fetching models: {e}"
            self.log(f"Error fetching models: {e}")
            return []

        return sorted(
            [
                {
                    "id": m["id"],
                    "name": m.get("display_name") or m["id"],
                    "context": m.get("context_window"),
                }
                for m in models
                if isinstance(m, dict) and m.get("id") and self._is_chat_model(m)
            ],
            key=lambda x: x["name"],
        )

    @staticmethod
    def _is_chat_model(model: dict) -> bool:
        """Keep chat routes only; embedding, image and speech routes cannot chat."""
        if model.get("model_type") in NON_CHAT_MODEL_TYPES:
            return False
        capabilities = model.get("capabilities")
        return not (isinstance(capabilities, dict) and capabilities.get("embeddings"))

    @staticmethod
    def _tooltip(model: dict) -> str:
        """Label a model, appending the context window only when the route reports one."""
        context = model.get("context")
        if isinstance(context, int) and not isinstance(context, bool) and context > 0:
            return f"{model['name']} ({context:,} tokens)"
        return model["name"]

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:
        """Refresh the model list when the key changes or the dropdown is refreshed."""
        if field_name not in {"api_key", "model_name", None}:
            return build_config

        models = self.fetch_models(field_value if field_name == "api_key" else None)
        if not models:
            # Discovery failed or no key is set yet. Leave the saved selection alone
            # rather than clearing a flow that works; ``status`` carries the reason.
            return build_config

        options = [m["id"] for m in models]
        build_config["model_name"]["options"] = options
        build_config["model_name"]["tooltips"] = {m["id"]: self._tooltip(m) for m in models}
        if build_config["model_name"].get("value") not in options:
            build_config["model_name"]["value"] = ""
        return build_config

    def build_model(self) -> LanguageModel:
        """Build the AnonRouter model."""
        api_key = secret_value_to_str(self.api_key, strip=True)
        if not api_key:
            msg = "API key is required"
            raise ValueError(msg)
        if not self.model_name:
            msg = "Please select a model"
            raise ValueError(msg)

        kwargs = {
            "model": self.model_name,
            "api_key": api_key,
            "base_url": BASE_URL,
            "temperature": self.temperature if self.temperature is not None else 0.7,
        }

        if self.max_tokens:
            kwargs["max_tokens"] = int(self.max_tokens)

        return ChatOpenAI(**kwargs)
