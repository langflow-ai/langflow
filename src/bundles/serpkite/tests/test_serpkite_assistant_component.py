"""Unit tests for the SerpKite AI Assistant component (``lfx-serpkite``).

``httpx.AsyncClient.post`` is patched at the component module to return real
``httpx.Response`` objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from lfx.schema.message import Message
from lfx_serpkite import SerpKiteAssistantComponent

POST_PATCH_TARGET = "lfx_serpkite.components.serpkite.serpkite_assistant.httpx.AsyncClient.post"

SAMPLE_PAYLOAD = {
    "request": {"prompt": "best crm", "endpoint": "chatgpt"},
    "text": "HubSpot is a common pick.",
    "markdown": "**HubSpot** is a common pick [1](https://example.com/crm).",
    "sources": [
        {"position": 1, "title": "CRM guide", "link": "https://example.com/crm"},
        {"position": 2, "title": "", "link": "https://example.org/list"},
        {"position": 3, "title": "No link"},
    ],
    "search_queries": [],
    "products": [],
    "meta": {"credits_used": 4},
}


def _response(url: str, status_code: int = 200, **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", url), **kwargs)


@pytest.fixture
def component() -> SerpKiteAssistantComponent:
    c = SerpKiteAssistantComponent()
    c.prompt = "best crm"
    c.assistant = "ChatGPT"
    c.serpkite_api_key = "test-key"  # pragma: allowlist secret
    c.country = ""
    return c


def test_component_metadata():
    """Class name must stay stable for saved flows."""
    assert SerpKiteAssistantComponent.__name__ == "SerpKiteAssistantComponent"


@pytest.mark.parametrize(
    ("assistant", "path"),
    [
        ("ChatGPT", "chatgpt"),
        ("Gemini", "gemini"),
        ("Copilot Search", "copilot"),
        ("Google AI Mode", "ai_mode"),
        ("Brave AI", "brave_ai"),
    ],
)
def test_posts_prompt_to_the_selected_assistant(component, assistant, path):
    component.assistant = assistant
    component.country = " de "
    url = f"https://api.serpkite.com/v1/{path}"
    mock_post = AsyncMock(return_value=_response(url, json=SAMPLE_PAYLOAD))
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert isinstance(message, Message)
    args, kwargs = mock_post.call_args
    assert args[0] == url
    assert kwargs["json"] == {"prompt": "best crm", "country": "de"}
    assert kwargs["headers"]["Authorization"] == "Bearer test-key"


def test_answer_includes_markdown_and_linked_sources(component):
    mock_post = AsyncMock(return_value=_response("https://api.serpkite.com/v1/chatgpt", json=SAMPLE_PAYLOAD))
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert message.text.startswith("**HubSpot** is a common pick")
    assert "Sources:\n1. [CRM guide](https://example.com/crm)" in message.text
    assert "2. [https://example.org/list](https://example.org/list)" in message.text
    assert "No link" not in message.text
    assert component.status == message.text


def test_answer_without_sources_is_just_the_answer(component):
    payload = {**SAMPLE_PAYLOAD, "sources": []}
    mock_post = AsyncMock(return_value=_response("https://api.serpkite.com/v1/chatgpt", json=payload))
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert message.text == SAMPLE_PAYLOAD["markdown"]


def test_empty_answer_is_explained(component):
    payload = {**SAMPLE_PAYLOAD, "text": "", "markdown": "", "sources": []}
    mock_post = AsyncMock(return_value=_response("https://api.serpkite.com/v1/brave_ai", json=payload))
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert message.text.startswith("The assistant returned no answer")


def test_missing_key_or_prompt_is_reported_without_a_request(component):
    mock_post = AsyncMock()
    component.serpkite_api_key = ""
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert "SerpKite key is required" in message.text
    component.serpkite_api_key = "test-key"  # pragma: allowlist secret
    component.prompt = "   "
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert "Prompt is required" in message.text
    mock_post.assert_not_called()


def test_too_long_prompt_and_unknown_assistant_are_rejected(component):
    mock_post = AsyncMock()
    component.prompt = "x" * 4001
    with patch(POST_PATCH_TARGET, mock_post):
        assert "longer than 4000" in asyncio.run(component.serpkite_ask_assistant()).text
    component.prompt = "ok"
    component.assistant = "Perplexity"
    with patch(POST_PATCH_TARGET, mock_post):
        assert "Unknown assistant" in asyncio.run(component.serpkite_ask_assistant()).text
    mock_post.assert_not_called()


def test_api_error_message_is_surfaced(component):
    body = {"error": {"code": "upstream_error", "message": "ChatGPT did not answer", "request_id": "r1"}}
    mock_post = AsyncMock(return_value=_response("https://api.serpkite.com/v1/chatgpt", 503, json=body))
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert message.text == "SerpKite error 503: ChatGPT did not answer"


def test_transport_error_is_surfaced(component):
    mock_post = AsyncMock(side_effect=httpx.ReadTimeout("timed out"))
    with patch(POST_PATCH_TARGET, mock_post):
        message = asyncio.run(component.serpkite_ask_assistant())
    assert message.text == "SerpKite error: timed out"
