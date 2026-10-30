"""Unit tests for the Asyntai extension bundle (``lfx-asyntai``).

The components call the Asyntai REST API with ``httpx.request``; the tests
patch it at the shared helper module to return real ``httpx.Response``
objects, so no network access is required.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import httpx
import pytest
from lfx_asyntai import AsyntaiAddKnowledgeComponent, AsyntaiAskComponent, AsyntaiLeadsComponent
from lfx_asyntai.components.asyntai.asyntai_leads import MAX_LIMIT, MIN_LIMIT

REQUEST_PATCH_TARGET = "lfx_asyntai.components.asyntai.asyntai_common.httpx.request"
API = "https://asyntai.com/api/v1"
KEY = "test-key"  # pragma: allowlist secret

LEADS_PAYLOAD = {
    "success": True,
    "leads": [
        {
            "session_id": "s1",
            "email": "ana@example.com",
            "phone": "",
            "page_url": "https://example.com/pricing",
            "started_at": "2026-10-01T10:00:00Z",
        },
        {
            "session_id": "s2",
            "email": "",
            "phone": "+420123456789",
            "page_url": "",
            "started_at": "2026-10-02T11:00:00Z",
        },
        "not-a-lead",
    ],
}


def _response(status_code: int = 200, method: str = "POST", **kwargs) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request(method, f"{API}/x/"), **kwargs)


def _mock(payload: object = None, status_code: int = 200, **kwargs) -> MagicMock:
    if payload is not None:
        kwargs["json"] = payload
    return MagicMock(return_value=_response(status_code, **kwargs))


@pytest.fixture
def ask() -> AsyntaiAskComponent:
    c = AsyntaiAskComponent()
    c.input_value = "What are your opening hours?"
    c.asyntai_api_key = KEY
    c.website = ""
    c.session_id = ""
    return c


@pytest.fixture
def add() -> AsyntaiAddKnowledgeComponent:
    c = AsyntaiAddKnowledgeComponent()
    c.url = ""
    c.title = ""
    c.content = ""
    c.asyntai_api_key = KEY
    c.website = ""
    return c


@pytest.fixture
def leads() -> AsyntaiLeadsComponent:
    c = AsyntaiLeadsComponent()
    c.asyntai_api_key = KEY
    c.since = ""
    c.website = ""
    c.limit = 50
    return c


# ---------------------------------------------------------------- metadata
def test_class_names_are_stable():
    """Class names must stay stable for saved flows."""
    assert AsyntaiAskComponent.__name__ == "AsyntaiAskComponent"
    assert AsyntaiAddKnowledgeComponent.__name__ == "AsyntaiAddKnowledgeComponent"
    assert AsyntaiLeadsComponent.__name__ == "AsyntaiLeadsComponent"


def test_api_key_inputs_are_secret():
    for component_class in (AsyntaiAskComponent, AsyntaiAddKnowledgeComponent, AsyntaiLeadsComponent):
        key_input = next(i for i in component_class.inputs if i.name == "asyntai_api_key")
        assert key_input.password is True
        assert key_input.required is True


# ---------------------------------------------------------------- ask
def test_ask_sends_bearer_key_and_question(ask):
    mock = _mock({"success": True, "response": "We are open 9-17.", "session_id": "api_1"})
    with patch(REQUEST_PATCH_TARGET, mock):
        message = ask.asyntai_ask_website()
    assert message.text == "We are open 9-17."
    args, kwargs = mock.call_args
    assert args == ("POST", f"{API}/chat/")
    assert kwargs["headers"]["Authorization"] == f"Bearer {KEY}"
    assert kwargs["headers"]["User-Agent"] == "langflow-asyntai-bundle"
    assert kwargs["json"] == {"message": "What are your opening hours?"}


def test_ask_includes_website_and_session(ask):
    ask.website = " example.com "
    ask.session_id = "flow-42"
    mock = _mock({"success": True, "response": "Yes."})
    with patch(REQUEST_PATCH_TARGET, mock):
        ask.asyntai_ask_website()
    assert mock.call_args.kwargs["json"] == {
        "message": "What are your opening hours?",
        "website_id": "example.com",
        "session_id": "flow-42",
    }


def test_ask_empty_question_makes_no_request(ask):
    ask.input_value = "   "
    mock = _mock({"success": True, "response": "x"})
    with patch(REQUEST_PATCH_TARGET, mock):
        message = ask.asyntai_ask_website()
    mock.assert_not_called()
    assert "Enter a question" in message.text


def test_ask_missing_key_makes_no_request(ask):
    ask.asyntai_api_key = ""
    mock = _mock({"success": True, "response": "x"})
    with patch(REQUEST_PATCH_TARGET, mock):
        message = ask.asyntai_ask_website()
    mock.assert_not_called()
    assert "API key is required" in message.text


@pytest.mark.parametrize(
    ("status", "payload", "expected"),
    [
        (401, {"success": False, "error": "Invalid API key"}, "rejected the API key"),
        (403, {"success": False, "error": "API access requires a paid plan"}, "requires a paid plan"),
        (429, {"success": False, "error": "Monthly message limit reached"}, "Monthly message limit"),
        (500, {"success": False, "error": "Server exploded"}, "Server exploded"),
    ],
)
def test_ask_surfaces_api_errors(ask, status, payload, expected):
    with patch(REQUEST_PATCH_TARGET, _mock(payload, status_code=status)):
        message = ask.asyntai_ask_website()
    assert expected in message.text


def test_ask_error_without_json_body(ask):
    with patch(REQUEST_PATCH_TARGET, _mock(status_code=502, text="<html>Bad gateway</html>")):
        message = ask.asyntai_ask_website()
    assert message.text == "Asyntai API error 502."


def test_ask_network_error(ask):
    failing = MagicMock(side_effect=httpx.ConnectError("boom"))
    with patch(REQUEST_PATCH_TARGET, failing):
        message = ask.asyntai_ask_website()
    assert "Could not reach the Asyntai API" in message.text


def test_ask_success_false_on_200(ask):
    with patch(REQUEST_PATCH_TARGET, _mock({"success": False, "error": "Website not found"})):
        message = ask.asyntai_ask_website()
    assert message.text == "Website not found"


def test_ask_non_object_payload(ask):
    with patch(REQUEST_PATCH_TARGET, _mock(["unexpected"])):
        message = ask.asyntai_ask_website()
    assert "unexpected response" in message.text


# ---------------------------------------------------------------- add knowledge
def test_add_url(add):
    add.url = "https://example.com/about"
    add.website = "7"
    mock = _mock({"success": True, "url": "https://example.com/about", "title": "About us", "chunks_created": 4})
    with patch(REQUEST_PATCH_TARGET, mock):
        result = add.asyntai_add_knowledge()
    args, kwargs = mock.call_args
    assert args == ("POST", f"{API}/knowledge/url/")
    assert kwargs["json"] == {"url": "https://example.com/about", "website_id": "7"}
    assert result.text == "Added 'About us' to the Asyntai knowledge base (4 chunks)."
    assert result.data["chunks_created"] == 4


def test_add_text(add):
    add.title = "Opening hours"
    add.content = "Monday to Friday, 9 to 17."
    mock = _mock({"success": True, "title": "Opening hours", "chunks_created": 1})
    with patch(REQUEST_PATCH_TARGET, mock):
        result = add.asyntai_add_knowledge()
    args, kwargs = mock.call_args
    assert args == ("POST", f"{API}/knowledge/text/")
    assert kwargs["json"] == {"title": "Opening hours", "content": "Monday to Friday, 9 to 17."}
    assert "Opening hours" in result.text


def test_add_text_without_title_uses_start_of_text(add):
    add.content = "Free delivery on orders over 50 EUR."
    mock = _mock({"success": True, "chunks_created": 1})
    with patch(REQUEST_PATCH_TARGET, mock):
        add.asyntai_add_knowledge()
    assert mock.call_args.kwargs["json"]["title"] == "Free delivery on orders over 50 EUR."


def test_add_url_wins_over_text(add):
    add.url = "https://example.com/faq"
    add.content = "ignored"
    mock = _mock({"success": True, "title": "FAQ"})
    with patch(REQUEST_PATCH_TARGET, mock):
        add.asyntai_add_knowledge()
    assert mock.call_args.args[1] == f"{API}/knowledge/url/"


def test_add_nothing_makes_no_request(add):
    mock = _mock({"success": True})
    with patch(REQUEST_PATCH_TARGET, mock):
        result = add.asyntai_add_knowledge()
    mock.assert_not_called()
    assert "error" in result.data


def test_add_surfaces_api_error(add):
    add.url = "https://example.com/blocked"
    payload = {"success": False, "error": "Could not read the page"}
    with patch(REQUEST_PATCH_TARGET, _mock(payload, status_code=400)):
        result = add.asyntai_add_knowledge()
    assert result.data["error"] == "Could not read the page"
    assert result.text == "Could not read the page"


# ---------------------------------------------------------------- leads
def test_leads_maps_rows_and_skips_malformed(leads):
    mock = _mock(LEADS_PAYLOAD, method="GET")
    with patch(REQUEST_PATCH_TARGET, mock):
        rows = leads.fetch_leads()
    args, kwargs = mock.call_args
    assert args == ("GET", f"{API}/leads/")
    assert kwargs["params"] == {"limit": 50}
    assert len(rows) == 2
    assert rows[0].data["email"] == "ana@example.com"
    assert rows[0].text == "ana@example.com on https://example.com/pricing"
    assert rows[1].text == "+420123456789"


def test_leads_passes_filters(leads):
    leads.since = "2026-10-01"
    leads.website = "example.com"
    mock = _mock({"success": True, "leads": []}, method="GET")
    with patch(REQUEST_PATCH_TARGET, mock):
        rows = leads.fetch_leads()
    assert rows == []
    assert mock.call_args.kwargs["params"] == {"limit": 50, "website_id": "example.com", "since": "2026-10-01"}


@pytest.mark.parametrize(("requested", "sent"), [(500, MAX_LIMIT), (0, MIN_LIMIT), (-3, MIN_LIMIT), (None, 50)])
def test_leads_limit_is_clamped(leads, requested, sent):
    leads.limit = requested
    mock = _mock({"success": True, "leads": []}, method="GET")
    with patch(REQUEST_PATCH_TARGET, mock):
        leads.fetch_leads()
    assert mock.call_args.kwargs["params"]["limit"] == sent


def test_leads_range_spec_matches_clamp():
    limit_input = next(i for i in AsyntaiLeadsComponent.inputs if i.name == "limit")
    assert limit_input.range_spec.min == MIN_LIMIT
    assert limit_input.range_spec.max == MAX_LIMIT


def test_leads_error_row(leads):
    with patch(REQUEST_PATCH_TARGET, _mock({"success": False, "error": "Invalid API key"}, status_code=401)):
        rows = leads.fetch_leads()
    assert len(rows) == 1
    assert "rejected the API key" in rows[0].data["error"]


def test_leads_dataframe_shape(leads):
    with patch(REQUEST_PATCH_TARGET, _mock(LEADS_PAYLOAD, method="GET")):
        frame = leads.asyntai_get_leads()
    assert list(frame["email"]) == ["ana@example.com", ""]
    assert {"email", "phone", "page_url", "started_at", "session_id"} <= set(frame.columns)


# ---------------------------------------------------------------- tool mode
def test_tool_names_are_asyntai_specific():
    """Agent-facing tool names must not collide with other components."""
    names = []
    for component in (
        AsyntaiAskComponent(asyntai_api_key=KEY),
        AsyntaiAddKnowledgeComponent(asyntai_api_key=KEY),
        AsyntaiLeadsComponent(asyntai_api_key=KEY, limit=50),
    ):
        names += [tool.name for tool in asyncio.run(component.to_toolkit())]
    assert names == ["asyntai_ask_website", "asyntai_add_knowledge", "asyntai_get_leads"]


def test_ask_tool_invocation():
    component = AsyntaiAskComponent(asyntai_api_key=KEY)
    tools = asyncio.run(component.to_toolkit())
    mock = _mock({"success": True, "response": "We ship to the EU."})
    with patch(REQUEST_PATCH_TARGET, mock):
        output = asyncio.run(tools[0].ainvoke({"input_value": "Do you ship to Germany?"}))
    assert mock.call_args.kwargs["json"] == {"message": "Do you ship to Germany?"}
    assert "We ship to the EU." in str(output)
