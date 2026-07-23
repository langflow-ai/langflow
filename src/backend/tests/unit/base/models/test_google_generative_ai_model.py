"""Regression tests for Gemini function-response compatibility in LFX."""

from langchain_core.messages import AIMessage, FunctionMessage, HumanMessage, ToolMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from lfx.base.models.google_generative_ai_model import (
    ChatGoogleGenerativeAIFixed,
    _ensure_function_response_names,
    _install_function_response_name_compat,
)
from lfx.base.models.unified_models.class_registry import get_model_class
from lfx.base.models.unified_models.instantiation import get_llm


def test_request_uses_fallback_name_for_unnamed_tool_response():
    model = ChatGoogleGenerativeAIFixed(model="gemini-2.5-flash", google_api_key="test-key")
    messages = [
        HumanMessage(content="Use the echo tool"),
        AIMessage(
            content="",
            tool_calls=[{"name": "echo", "args": {"text": "hello"}, "id": "call-1", "type": "tool_call"}],
        ),
        ToolMessage(content="hello", tool_call_id="call-1"),
    ]

    request = model._prepare_request(messages)

    function_response = request["contents"][-1].parts[0].function_response
    assert function_response.name == "tool_response"


def test_ensure_function_response_names_handles_tool_and_function_messages():
    tool_message = ToolMessage(content="tool output", tool_call_id="call-1")
    function_message = FunctionMessage(content="function output", name="")
    human_message = HumanMessage(content="hello")

    fixed_messages = _ensure_function_response_names([tool_message, function_message, human_message])

    assert fixed_messages[0].name == "tool_response"
    assert fixed_messages[1].name == "function_response"
    assert fixed_messages[2] is human_message
    assert tool_message.name is None
    assert function_message.name == ""


def test_agent_registry_resolves_compat_class():
    assert get_model_class("ChatGoogleGenerativeAIFixed") is ChatGoogleGenerativeAIFixed


def test_unified_language_model_builds_google_compat_class():
    model = get_llm(
        [
            {
                "name": "gemini-2.5-flash",
                "provider": "Google Generative AI",
                "metadata": {
                    "model_class": "ChatGoogleGenerativeAIFixed",
                    "model_name_param": "model",
                    "api_key_param": "google_api_key",  # pragma: allowlist secret
                },
            }
        ],
        user_id=None,
        api_key="test-key",  # pragma: allowlist secret
    )

    assert type(model) is ChatGoogleGenerativeAIFixed


def test_compat_reuses_parent_pydantic_model_and_defaults():
    assert ChatGoogleGenerativeAIFixed is ChatGoogleGenerativeAI
    required_fields = {name for name, field in ChatGoogleGenerativeAIFixed.model_fields.items() if field.is_required()}
    assert required_fields == {"model"}
    assert ChatGoogleGenerativeAIFixed.model_fields["temperature"].default == 0.7


def test_compat_install_is_idempotent():
    request_hook = getattr(ChatGoogleGenerativeAI, "_prepare_request")  # noqa: B009
    assert _install_function_response_name_compat() is ChatGoogleGenerativeAI
    assert getattr(ChatGoogleGenerativeAI, "_prepare_request") is request_hook  # noqa: B009
