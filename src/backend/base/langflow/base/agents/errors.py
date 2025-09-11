from anthropic import BadRequestError as AnthropicBadRequestError
from cohere import BadRequestError as CohereBadRequestError
from httpx import HTTPStatusError

from langflow.schema.message import Message


class CustomBadRequestError(AnthropicBadRequestError, CohereBadRequestError, HTTPStatusError):
    def __init__(self, agent_message: Message | None, message: str):
        super().__init__(message)
        self.message = message
        self.agent_message = agent_message

    def __str__(self):
        return f"{self.message}"
