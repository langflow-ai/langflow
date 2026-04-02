"""AG2 LLM Configuration component for Langflow."""

import os

from lfx.custom.custom_component.component import Component
from lfx.io import DropdownInput, MessageTextInput, Output, SecretStrInput


class AG2LLMConfigComponent(Component):
    display_name = "AG2 LLM Config"
    description = "Configure the LLM provider and model for AG2 agents."
    icon = "AG2"
    name = "AG2LLMConfig"

    inputs = [
        MessageTextInput(
            name="model",
            display_name="Model",
            info="LLM model name.",
            value="gpt-4o-mini",
        ),
        SecretStrInput(
            name="api_key",
            display_name="API Key",
            info="API key for the LLM provider. Falls back to OPENAI_API_KEY env var.",
            value="",
        ),
        DropdownInput(
            name="api_type",
            display_name="API Type",
            info="LLM provider type.",
            options=["openai", "anthropic", "bedrock", "azure"],
            value="openai",
        ),
        MessageTextInput(
            name="base_url",
            display_name="Base URL (optional)",
            info="Custom API base URL for OpenAI-compatible endpoints.",
            value="",
            advanced=True,
        ),
    ]

    outputs = [
        Output(display_name="LLM Config", name="llm_config", method="build_config", types=["Data"]),
    ]

    def build_config(self):
        api_key = self.api_key or os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            msg = "API key is required. Provide it in the component or set OPENAI_API_KEY."
            raise ValueError(msg)

        try:
            from autogen import LLMConfig
        except ImportError as e:
            msg = 'AG2 is not installed. Run: pip install "ag2[openai]>=0.11.4,<1.0"'
            raise ImportError(msg) from e

        config = {
            "model": self.model,
            "api_key": api_key,
            "api_type": self.api_type,
        }
        if self.base_url:
            config["base_url"] = self.base_url

        llm_config = LLMConfig(config)
        self.status = f"LLMConfig: {self.model} ({self.api_type})"
        return llm_config
