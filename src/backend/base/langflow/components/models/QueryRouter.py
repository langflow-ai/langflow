import httpx
from typing import Any

from langchain_openai import ChatOpenAI
from pydantic.v1 import SecretStr

from lfx.base.models.model import LCModelComponent
from lfx.field_typing import LanguageModel
from lfx.inputs.inputs import BoolInput, DictInput, DropdownInput, IntInput, SecretStrInput, SliderInput, StrInput
from lfx.log.logger import logger


class QueryRouterModelComponent(LCModelComponent):
    display_name = "QueryRouter"
    description = "Generates text using QueryRouter API - OpenAI-compatible interface."
    icon = "Globe"
    name = "QueryRouterModel"
    API_BASE = "https://api.queryrouter.ru/v1"

    inputs = [
        *LCModelComponent.get_base_inputs(),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            advanced=True,
            info="The maximum number of tokens to generate. Set to 0 for unlimited tokens.",
        ),
        DictInput(
            name="model_kwargs",
            display_name="Model Kwargs",
            advanced=True,
            info="Additional keyword arguments to pass to the model.",
        ),
        BoolInput(
            name="json_mode",
            display_name="JSON Mode",
            advanced=True,
            info="If True, it will output JSON regardless of passing a schema.",
        ),
        DropdownInput(
            name="model_name",
            display_name="Model Name",
            advanced=False,
            options=[],  # Will be populated dynamically from /v1/models
            value="gpt-4o",
            combobox=True,
            real_time_refresh=True,
            info="Model to use for generation. Models are fetched from QueryRouter API.",
        ),
        SecretStrInput(
            name="api_key",
            display_name="QueryRouter API Key",
            info="Your QueryRouter API key for authentication. If not provided, the default key from SSO will be used.",
            advanced=False,
            value="",
            required=False,
        ),
        SliderInput(
            name="temperature",
            display_name="Temperature",
            value=0.1,
            range_spec={"min": 0, "max": 1, "step": 0.01},
            show=True,
        ),
        IntInput(
            name="seed",
            display_name="Seed",
            info="The seed controls the reproducibility of the job.",
            advanced=True,
            value=1,
        ),
        IntInput(
            name="max_retries",
            display_name="Max Retries",
            info="The maximum number of retries to make when generating.",
            advanced=True,
            value=5,
        ),
        IntInput(
            name="timeout",
            display_name="Timeout",
            info="The timeout for requests to QueryRouter API.",
            advanced=True,
            value=700,
        ),
    ]

    def fetch_models(self) -> list[dict]:
        """Fetch available models from QueryRouter."""
        models_url = f"{self.API_BASE}/models"
        try:
            # We need to provide an API key to fetch models,
            # so we'll try to get it from the input or variables.
            api_key_value = None
            if self.api_key:
                if isinstance(self.api_key, SecretStr):
                    api_key_value = self.api_key.get_secret_value()
                else:
                    api_key_value = str(self.api_key)
            
            if not api_key_value:
                from lfx.services.deps import get_variable_service
                variable_service = get_variable_service()
                if variable_service:
                    try:
                        api_key_value = variable_service.get_variable(name="queryrouter_api_key")
                    except ValueError:
                        pass # It's okay if it's not found here, we'll log later

            headers = {}
            if api_key_value:
                headers["Authorization"] = f"Bearer {api_key_value}"

            response = httpx.get(models_url, headers=headers, timeout=10.0)
            response.raise_for_status()
            models = response.json().get("data", [])
            return sorted(
                [
                    {
                        "id": m["id"],
                        "name": m.get("display_name", m["id"]),
                        "context": m.get("context_length", "N/A"),
                    }
                    for m in models
                    if m.get("id")
                ],
                key=lambda x: x["name"],
            )
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Error fetching QueryRouter models: {e}")
            return []

    def update_build_config(self, build_config: dict, field_value: str, field_name: str | None = None) -> dict:  # noqa: ARG002
        """Update model options."""
        models = self.fetch_models()
        if models:
            build_config["model_name"]["options"] = [m["id"] for m in models]
            build_config["model_name"]["tooltips"] = {m["id"]: f"{m['name']} ({m['context']} tokens)" for m in models}
        else:
            build_config["model_name"]["options"] = ["Failed to load models"]
            build_config["model_name"]["value"] = "Failed to load models"
        return build_config

    def build_model(self) -> LanguageModel:  # type: ignore[type-var]
        logger.debug(f"Executing request with model: {self.model_name}")
        # Handle api_key - it can be string or SecretStr
        api_key_value = None
        if self.api_key:
            if isinstance(self.api_key, SecretStr):
                api_key_value = self.api_key.get_secret_value()
            else:
                api_key_value = str(self.api_key)
        
        if not api_key_value:
            # If no API key is provided in the component's input,
            # try to get it from the variable service, where it should
            # have been stored after SSO.
            from lfx.services.deps import get_variable_service
            variable_service = get_variable_service()
            if variable_service:
                # The variable name 'queryrouter_api_key' is a convention
                # we need to establish.
                try:
                    api_key_value = variable_service.get_variable(name="queryrouter_api_key")
                except ValueError:
                    logger.warning("QueryRouter API Key not found in variables. Please configure it manually or perform SSO.")

        if not api_key_value:
            raise ValueError("QueryRouter API Key is required. Please provide one in the component settings or perform SSO.")


        # Build the model
        # Assemble kwargs like OpenRouter: only pass max_tokens if valid integer
        kwargs: dict[str, Any] = {
            "model": self.model_name or "gpt-4o",
            "openai_api_key": api_key_value,
            "openai_api_base": self.API_BASE,
            "temperature": self.temperature if self.temperature is not None else 0.1,
            "seed": self.seed,
            "max_retries": self.max_retries,
            "request_timeout": self.timeout,
            "model_kwargs": self.model_kwargs or {},
        }
        if getattr(self, "max_tokens", None) not in (None, "", 0):
            try:
                kwargs["max_tokens"] = int(self.max_tokens)
            except (TypeError, ValueError):
                pass

        model = ChatOpenAI(**kwargs)

        if self.json_mode:
            model = model.bind(response_format={"type": "json_object"})

        return model
