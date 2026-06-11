"""Google Gemini chat LLM service component (text)."""

from lfx.base.pipecat.service import PipecatServiceComponent
from lfx.field_typing.voice_types import PipecatLLMService
from lfx.io import DropdownInput, HandleInput, Output, SecretStrInput


class GoogleLLMServiceComponent(PipecatServiceComponent):
    display_name = "Google Gemini LLM"
    description = "Google Gemini chat completion LLM (text)."
    icon = "BotMessageSquare"
    name = "GoogleLLM"

    inputs = [
        SecretStrInput(name="api_key", display_name="Google API Key", required=True),
        DropdownInput(
            name="model",
            display_name="Model",
            options=[
                "gemini-2.5-flash",
                "gemini-2.5-pro",
                "gemini-2.0-flash",
            ],
            value="gemini-2.5-flash",
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
        from pipecat.services.google.llm import GoogleLLMService

        service = GoogleLLMService(api_key=self.api_key, model=self.model)
        self._register_tools(service)
        return service
