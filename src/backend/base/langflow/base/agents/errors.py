from anthropic import BadRequestError as AnthropicBadRequestError
from cohere import BadRequestError as CohereBadRequestError
from httpx import HTTPStatusError


class CustomBadRequestError(AnthropicBadRequestError, CohereBadRequestError,HTTPStatusError):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message
