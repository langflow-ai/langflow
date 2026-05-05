"""Tests for the AgentExecutor input-shape fallback in `LCAgentComponent._build_graph_input`.

When the resolved runnable is a `langchain_classic.AgentExecutor` (kept as a
transitional path for the legacy SQL/JSON/OpenAPI/VectorStoreRouter agent
components), `_build_graph_input` must produce the legacy
`{"input": str, "chat_history": [BaseMessage]}` shape — NOT the modern
`{"messages": [...]}` shape that `create_agent` graphs expect.

Covers reviewer feedback on PR #12982.
"""

from unittest.mock import MagicMock

import pytest
from langchain_classic.agents import AgentExecutor
from langchain_core.messages import HumanMessage
from lfx.base.agents.agent import (
    LCAgentComponent,
    _build_legacy_executor_input,
    _coerce_input_to_text,
    _is_legacy_agent_executor,
)
from lfx.schema.message import Message

# --- _is_legacy_agent_executor ---------------------------------------------------------


def test_should_return_true_when_runnable_is_agent_executor() -> None:
    fake_executor = MagicMock(spec=AgentExecutor)
    assert _is_legacy_agent_executor(fake_executor) is True
    # Negative-side coverage: anything else (including None) must NOT match.
    assert _is_legacy_agent_executor(MagicMock()) is False
    assert _is_legacy_agent_executor(None) is False


def test_should_return_false_when_langchain_classic_is_not_installed(monkeypatch) -> None:
    """The lazy `from langchain_classic.agents import AgentExecutor` may fail in slim deployments.

    Covers the ImportError branch in `_is_legacy_agent_executor` so that a missing
    `langchain_classic` does not crash the modern stack — it simply means "no legacy
    executor in play".
    """
    import builtins

    real_import = builtins.__import__

    def _fake_import(name, *args, **kwargs):
        if name.startswith("langchain_classic"):
            msg = f"No module named {name!r}"
            raise ImportError(msg)
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    assert _is_legacy_agent_executor(MagicMock()) is False


# --- _coerce_input_to_text -------------------------------------------------------------


def test_should_extract_text_attr_when_present() -> None:
    msg = Message(text="hello")
    assert _coerce_input_to_text(msg) == "hello"


def test_should_extract_string_content_when_no_text_attr() -> None:
    obj = MagicMock(spec=["content"])
    obj.content = "raw content"
    assert _coerce_input_to_text(obj) == "raw content"


def test_should_join_text_parts_when_content_is_multimodal_list() -> None:
    """Drop image parts and join text parts when AgentExecutor needs a plain string.

    AgentExecutor only accepts `input: str`. Legacy SQL/JSON/OpenAPI agents don't
    consume images anyway, so the multimodal parts are joined into plain text.
    """
    obj = MagicMock(spec=["content"])
    obj.content = [
        {"type": "text", "text": "first"},
        {"type": "image_url", "image_url": {"url": "..."}},
        {"type": "text", "text": "second"},
    ]
    assert _coerce_input_to_text(obj) == "first second"


# --- _build_legacy_executor_input ------------------------------------------------------


def test_should_return_input_dict_with_extracted_text_when_no_history() -> None:
    msg = Message(text="What is 2+2?")
    payload = _build_legacy_executor_input(msg, None)

    assert payload == {"input": "What is 2+2?"}


def test_should_inject_continue_message_when_input_is_blank() -> None:
    payload = _build_legacy_executor_input(Message(text="   "), None)

    assert payload["input"] == "Continue the conversation."


def test_should_include_chat_history_as_lc_messages_when_provided() -> None:
    msg = Message(text="follow up?")
    history_item = MagicMock()
    history_item.text = "prev message"
    history_item.to_lc_message = MagicMock(return_value=HumanMessage(content="prev message"))

    payload = _build_legacy_executor_input(msg, [history_item])

    assert payload["input"] == "follow up?"
    assert "chat_history" in payload
    assert len(payload["chat_history"]) == 1
    assert isinstance(payload["chat_history"][0], HumanMessage)


def test_should_skip_history_items_with_empty_text() -> None:
    msg = Message(text="hi")
    blank_item = MagicMock()
    blank_item.text = "   "
    blank_item.to_lc_message = MagicMock(return_value=HumanMessage(content=""))

    payload = _build_legacy_executor_input(msg, [blank_item])

    # blank item must NOT be in chat_history; key omitted entirely when empty
    assert "chat_history" not in payload or payload.get("chat_history") == []


# --- LCAgentComponent._build_graph_input (dispatch) ------------------------------------


class _ConcreteAgentComponent(LCAgentComponent):
    """Minimal concrete subclass exposing the abstract methods for instantiation."""

    def build_agent(self):  # pragma: no cover - not exercised
        raise NotImplementedError

    def create_agent_runnable(self):  # pragma: no cover - not exercised
        raise NotImplementedError


@pytest.fixture
def component() -> _ConcreteAgentComponent:
    component = _ConcreteAgentComponent()
    component.input_value = Message(text="ping")
    return component


def test_should_return_messages_payload_when_runnable_is_compiled_graph(component) -> None:
    """Modern path: any non-AgentExecutor runnable triggers the `{"messages": [...]}` shape."""
    payload = component._build_graph_input(MagicMock())

    assert "messages" in payload
    assert "input" not in payload


def test_should_return_legacy_payload_when_runnable_is_agent_executor(component) -> None:
    """Reviewer's blocker: AgentExecutor MUST receive `{"input": str}`, not `{"messages": ...}`."""
    fake_executor = MagicMock(spec=AgentExecutor)

    payload = component._build_graph_input(fake_executor)

    assert "input" in payload
    assert payload["input"] == "ping"
    assert "messages" not in payload
