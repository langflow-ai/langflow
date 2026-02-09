from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import messages_from_dict
from toolguard.buildtime.llm import LanguageModelBase


class LangchainModelWrapper(LanguageModelBase):
    """Wrapper for Langchain chat models to work with ToolGuard.

    This wrapper handles:
    - Message format conversion between ToolGuard and Langchain
    - Automatic continuation when max tokens are reached
    - Safe error handling and validation
    """

    MAX_CONTINUATIONS = 5  # Prevent infinite recursion
    DEFAULT_MAX_OUT_TOKENS = 16000

    def __init__(self, langchain_model: BaseChatModel):
        """Initialize the wrapper with a Langchain chat model.

        Args:
            langchain_model: A Langchain BaseChatModel instance
        """
        self.langchain_model = langchain_model
        if hasattr(self.langchain_model, "max_tokens") and getattr(self.langchain_model, "max_tokens", None) is None:
            self.langchain_model.max_tokens = self.DEFAULT_MAX_OUT_TOKENS

    def _convert_role(self, role: str) -> str:
        """Convert ToolGuard role to Langchain message type.

        Args:
            role: The role from ToolGuard format ("user", "assistant", "system")

        Returns:
            Langchain message type ("human", "ai", "system")
        """
        role_mapping = {
            "user": "human",
            "assistant": "ai",
            "system": "system",
        }
        return role_mapping.get(role, "system")

    def _validate_messages(self, messages: list[dict]) -> None:
        """Validate message format.

        Args:
            messages: List of message dictionaries

        Raises:
            ValueError: If messages are invalid
        """
        if not isinstance(messages, list):
            msg = f"Messages must be a list, got {type(messages)}"
            raise TypeError(msg)

        for i, msg in enumerate(messages):
            if not isinstance(msg, dict):
                error_msg = f"Message at index {i} must be a dict, got {type(msg)}"
                raise TypeError(error_msg)

            if "role" not in msg:
                error_msg = f"Message at index {i} missing 'role' field"
                raise ValueError(error_msg)

            if "content" not in msg:
                error_msg = f"Message at index {i} missing 'content' field"
                raise ValueError(error_msg)

    def _extract_content(self, content: Any) -> str:
        """Safely extract string content from various types.

        Args:
            content: Content that could be str, list, tuple, or None

        Returns:
            String representation of the content
        """
        if content is None:
            return ""

        if isinstance(content, str):
            return content

        if isinstance(content, (list, tuple)):
            # Join list/tuple elements with space
            return " ".join(str(item) for item in content)

        return str(content)

    async def generate(self, messages: list[dict], _recursion_depth: int = 0) -> str:
        """Generate a response from the language model.

        Args:
            messages: List of message dicts with 'role' and 'content' keys
            _recursion_depth: Internal counter to prevent infinite recursion

        Returns:
            Generated text response

        Raises:
            ValueError: If messages are invalid or response is malformed
            RuntimeError: If max continuations exceeded or API call fails
        """
        # Validate inputs
        self._validate_messages(messages)

        # Check recursion depth
        if _recursion_depth >= self.MAX_CONTINUATIONS:
            msg = f"Maximum continuation depth ({self.MAX_CONTINUATIONS}) exceeded"
            raise RuntimeError(msg)

        # Convert messages to Langchain format
        converted_messages = [
            {
                "type": self._convert_role(msg.get("role", "system")),
                "data": {"content": self._extract_content(msg.get("content"))},
            }
            for msg in messages
        ]

        try:
            lc_messages = messages_from_dict(converted_messages)
        except Exception as exc:
            msg = f"Failed to convert messages to Langchain format: {exc}"
            raise ValueError(msg) from exc

        # Call the language model
        try:
            response = await self.langchain_model.agenerate(
                messages=[lc_messages],
            )
        except Exception as exc:
            msg = f"Language model API call failed: {exc}"
            raise RuntimeError(msg) from exc

        # Safely extract response
        if not response.generations or not response.generations[0]:
            msg = "Empty response from language model"
            raise ValueError(msg)

        choice0 = response.generations[0][0]

        if not hasattr(choice0, "message") or not hasattr(choice0.message, "content"):
            msg = "Malformed response from language model"
            raise ValueError(msg)

        chunk = self._extract_content(choice0.message.content)

        # Check if we need to continue due to max tokens
        generation_info = getattr(choice0, "generation_info", None)
        if generation_info and isinstance(generation_info, dict):
            finish_reason = generation_info.get("finish_reason")

            if finish_reason == "length":  # max tokens reached
                resp_msg = {
                    "role": "assistant",
                    "content": chunk,
                }
                continue_msg = {
                    "role": "user",
                    "content": (
                        "Continue the previous answer starting exactly from the last incomplete sentence. "
                        "Do not repeat anything. Do not add any prefix."
                    ),
                }
                next_messages = [
                    *messages,
                    resp_msg,
                    continue_msg,
                ]

                # Recursive call with depth tracking
                continuation = await self.generate(next_messages, _recursion_depth + 1)
                return chunk + continuation

        return chunk


# Made with Bob
