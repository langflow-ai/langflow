"""Anthropic (Claude) chat LLM service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatLLMService
from lfx.io import DropdownInput, HandleInput, Output, SecretStrInput


class AnthropicLLMServiceComponent(PipecatServiceComponent):
    display_name = "Anthropic LLM"
    description = "Anthropic Claude chat completion LLM."
    icon = "BotMessageSquare"
    name = "AnthropicLLM"

    inputs = [
        SecretStrInput(name="api_key", display_name="Anthropic API Key", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            options=[
                "claude-opus-4-7",
                "claude-sonnet-4-6",
                "claude-haiku-4-5-20251001",
                "claude-3-5-sonnet-latest",
            ],
            value="claude-haiku-4-5-20251001",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["PipecatTool"],
            is_list=True,
            required=False,
        ),
    ]

    outputs = [
        Output(
            display_name="LLM",
            name="llm",
            method="build_service",
            types=["PipecatLLMService", "PipecatFrameProcessor"],
        ),
    ]

    def build_service(self) -> PipecatLLMService:
        from pipecat.services.anthropic.llm import AnthropicLLMService

        service = AnthropicLLMService(api_key=self.api_key, model=self.model)
        self._register_tools(service)
        return service
