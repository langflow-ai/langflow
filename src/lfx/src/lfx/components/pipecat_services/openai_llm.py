"""OpenAI chat LLM service component."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatLLMService
from lfx.io import DropdownInput, HandleInput, Output, SecretStrInput


class OpenAILLMServiceComponent(PipecatServiceComponent):
    display_name = "OpenAI LLM"
    description = "OpenAI chat completion LLM (gpt-4o, gpt-4o-mini, etc.)."
    icon = "BotMessageSquare"
    name = "OpenAILLM"

    inputs = [
        SecretStrInput(name="api_key", display_name="OpenAI API Key", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            options=["gpt-4o", "gpt-4o-mini", "gpt-4.1", "gpt-4.1-mini", "gpt-5", "gpt-5-mini"],
            value="gpt-4o-mini",
        ),
        HandleInput(
            name="tools",
            display_name="Tools",
            input_types=["PipecatTool"],
            is_list=True,
            required=False,
            info="VoiceTool outputs to register on this LLM.",
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
        # OpenAI SDK reads OPENAI_API_KEY from the env; pass via kwargs.
        from pipecat.services.openai.llm import OpenAILLMService

        service = OpenAILLMService(
            settings=OpenAILLMService.Settings(model=self.model),
            api_key=self.api_key,
        )
        self._register_tools(service)
        return service
