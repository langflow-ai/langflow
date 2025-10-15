from unittest.mock import MagicMock

from langchain_core.language_models import BaseLanguageModel
from typing_extensions import override

from pydantic import BaseModel, Field


class MockLanguageModel(BaseLanguageModel, BaseModel):
    """A mock language model for testing purposes."""

    tools: list = Field(default_factory=list)
    response_generator: callable = Field(default_factory=lambda: lambda msg: f"Response for {msg}")

    def __init__(self, response_generator=None, **kwargs):
        """Initialize the mock model with an optional response generator function."""
        super().__init__(**kwargs)
        if response_generator:
            self.response_generator = response_generator

    @override
    def with_config(self, *args, **kwargs):
        return self

    @override
    def with_structured_output(self, *args, **kwargs):
        return self

    @override
    async def abatch(self, messages, *args, **kwargs):
        if not messages:
            return []
        # If message is a list of dicts (chat format), get the last user message
        responses = []
        for msg_list in messages:
            content = msg_list[-1]["content"] if isinstance(msg_list, list) else msg_list
            mock_response = MagicMock()
            mock_response.content = self.response_generator(content)
            responses.append(mock_response)
        return responses

    @override
    def invoke(self, *args, **kwargs):
        return self

    @override
    def generate_prompt(self, *args, **kwargs):
        raise NotImplementedError

    @override
    async def agenerate_prompt(self, *args, **kwargs):
        raise NotImplementedError

    @override
    def predict(self, *args, **kwargs):
        raise NotImplementedError

    @override
    def predict_messages(self, *args, **kwargs):
        raise NotImplementedError

    @override
    async def apredict(self, *args, **kwargs):
        raise NotImplementedError

    @override
    async def apredict_messages(self, *args, **kwargs):
        raise NotImplementedError

    def bind_tools(self, tools, tool_choice=None):  # noqa: ARG002
        """Bind tools to the model for testing."""
        self.tools = tools
        return self
