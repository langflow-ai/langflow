"""AI Gateway Component - Unified AI model access through AI Gateway."""

from langflow.custom import Component
from langflow.custom.genesis.services.deps import get_ai_gateway_service
from langflow.io import (
    DropdownInput,
    FloatInput,
    HandleInput,
    IntInput,
    MessageTextInput,
    MultilineInput,
    Output,
    SecretStrInput,
)
from langflow.schema.message import Message


class AIGatewayComponent(Component):
    """AI Gateway - Unified access to multiple AI providers through AI Gateway."""

    display_name: str = "AI Gateway"
    description: str = "Universal AI model access supporting multiple providers through AI Gateway"
    icon: str = "Brain"
    name: str = "AIGateway"
    beta: bool = False

    inputs = [
        DropdownInput(
            name="provider",
            display_name="Model Provider",
            info="Select from available AI providers",
            options=[],
            placeholder="Select a provider",
            refresh_button=True,
            real_time_refresh=True,
            input_types=[],
            required=True,
        ),
        DropdownInput(
            name="model_name",
            display_name="Model",
            info="Select the AI model to use",
            options=[],
            placeholder="Select a model",
            show=False,
            required=True,
        ),
        MultilineInput(
            name="system_prompt",
            display_name="Agent Instructions",
            info="System Prompt: Initial instructions and context provided to guide the AI behavior.",
            value="You are a helpful assistant that can use tools to answer questions and perform tasks.",
            advanced=False,
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["Tool"],
            is_list=True,
            required=False,
            info="Tools that can be used by the AI model",
        ),
        MessageTextInput(
            name="input_value",
            display_name="Input",
            info="Message to send to the AI model",
        ),
        SecretStrInput(
            name="apiKey",
            display_name="API Key",
            info="API key for the selected model",
            show=False,
            required=True,
        ),
        FloatInput(
            name="temperature",
            display_name="Temperature",
            info="Controls randomness in responses",
            value=0.7,
            show=False,
        ),
        IntInput(
            name="max_tokens",
            display_name="Max Tokens",
            info="Maximum number of tokens to generate",
            value=1000,
            show=False,
        ),
    ]

    outputs = [Output(name="response", display_name="Response", method="generate_response")]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ai_gateway_service = None

    def _get_ai_gateway_service(self):
        """Get AI Gateway service instance."""
        if self._ai_gateway_service is None:
            self._ai_gateway_service = get_ai_gateway_service()
        return self._ai_gateway_service

    async def update_build_config(self, build_config, field_value, field_name=None):
        """Update build configuration based on field changes."""
        service = self._get_ai_gateway_service()

        if field_name == "provider":
            build_config["provider"]["options"] = service.get_providers()

            if field_value:
                model_names = service.get_models(field_value)
                model_options = [f"{name} ({service.get_base_model(name)})" for name in model_names]
                build_config["model_name"]["options"] = model_options
                build_config["model_name"]["show"] = True
                build_config["apiKey"]["show"] = True
                build_config["temperature"]["show"] = True
                build_config["max_tokens"]["show"] = True

        return build_config

    def generate_response(self) -> Message:
        """Generate AI response through AI Gateway."""
        if not self.provider or not self.model_name or not self.apiKey:
            error_message = "Provider, model, and API key must be provided"
            raise ValueError(error_message)

        service = self._get_ai_gateway_service()

        # Extract model name from dropdown option
        model_name = self.model_name.split(" (")[0] if " (" in self.model_name else self.model_name

        response = service.chat_completion(
            model_name=model_name,
            messages=[{"role": "system", "content": self.system_prompt}, {"role": "user", "content": self.input_value}],
            api_key=self.apiKey,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
        )

        # Return just the text content
        return response["choices"][0]["message"]["content"]
