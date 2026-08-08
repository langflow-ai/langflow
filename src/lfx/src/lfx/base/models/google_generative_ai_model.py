"""Google Generative AI request compatibility helpers.

Keep the upstream Pydantic model intact while normalizing empty function
response names before LangChain prepares a Gemini request.
"""

from typing import Any

from langchain_google_genai import ChatGoogleGenerativeAI


def _ensure_function_response_names(messages: list[Any]) -> list[Any]:
    """Return messages with fallback names for unnamed function responses."""
    from langchain_core.messages import FunctionMessage, ToolMessage

    fixed_messages = []
    for message in messages:
        fixed_message = message
        if isinstance(message, ToolMessage) and not message.name:
            fixed_message = ToolMessage(
                content=message.content,
                name="tool_response",
                tool_call_id=getattr(message, "tool_call_id", None),
                artifact=getattr(message, "artifact", None),
            )
        elif isinstance(message, FunctionMessage) and not message.name:
            fixed_message = FunctionMessage(content=message.content, name="function_response")
        fixed_messages.append(fixed_message)
    return fixed_messages


def _install_function_response_name_compat() -> type[ChatGoogleGenerativeAI]:
    """Patch Gemini request preparation once without rebuilding its Pydantic model."""
    original_prepare_request = getattr(ChatGoogleGenerativeAI, "_prepare_request")  # noqa: B009
    if getattr(original_prepare_request, "__lfx_function_response_name_compat__", False):
        return ChatGoogleGenerativeAI

    def prepare_request_with_function_response_names(
        self: ChatGoogleGenerativeAI, messages: list[Any], *args: Any, **kwargs: Any
    ) -> dict[str, Any]:
        fixed_messages = _ensure_function_response_names(messages)
        return original_prepare_request(self, fixed_messages, *args, **kwargs)

    setattr(prepare_request_with_function_response_names, "__lfx_function_response_name_compat__", True)  # noqa: B010
    setattr(ChatGoogleGenerativeAI, "_prepare_request", prepare_request_with_function_response_names)  # noqa: B010
    return ChatGoogleGenerativeAI


# Do not subclass ChatGoogleGenerativeAI here. Pydantic 2.14 can leave its
# inherited fields deferred during server startup, making a local subclass
# incomplete. Patch the request hook once and retain the upstream model's
# already-complete fields, defaults, and validators.
ChatGoogleGenerativeAIFixed = _install_function_response_name_compat()
