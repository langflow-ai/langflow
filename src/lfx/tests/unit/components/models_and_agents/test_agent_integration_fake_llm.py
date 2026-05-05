"""Integration tests: AgentComponent end-to-end with a scripted fake LLM.

These tests exercise the full pipeline:
  build_initial_messages → create_agent (langgraph) → astream_events → process_agent_events → Message

The LLM is scripted (no API key, no network) but everything else is real:
- The CompiledStateGraph from `langchain.agents.create_agent`
- The middleware wiring (ModelCallLimitMiddleware, ToolRetryMiddleware)
- The event processing (events.py: handle_on_chain_*, handle_on_tool_*)
- The Message construction with content_blocks (Agent Steps)

Each test corresponds to a smoke from CZL/MANUAL_TESTING_create_agent_migration.md
that previously had to be validated by clicking through the Playground. Automating
them means every PR runs them in seconds — the bugs we caught manually
(empty-input replay, etc.) become permanent regression guards.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatResult
from langchain_core.tools import BaseTool
from lfx.components.langchain_utilities.tool_calling import ToolCallingAgentComponent
from lfx.schema.content_types import TextContent, ToolContent
from lfx.schema.data import Data
from lfx.schema.message import Message
from lfx.utils.constants import MESSAGE_SENDER_AI, MESSAGE_SENDER_USER
from pydantic import Field

# ============================================================================
# Test infrastructure: scripted fake LLM that records inputs
# ============================================================================


class ScriptedFakeChatModel(FakeMessagesListChatModel):
    """Fake LLM that emits a scripted sequence of AIMessages and records every input.

    Test pattern:
        model = ScriptedFakeChatModel(responses=[
            AIMessage(content="", tool_calls=[{"name": "calc", "args": {"x": 17}, "id": "1"}]),
            AIMessage(content="The answer is 391"),
        ])
        # use model in agent flow
        # then assert:
        assert len(model.received_inputs) == 2
        assert isinstance(model.received_inputs[0][-1], HumanMessage)
    """

    received_inputs: list[list[BaseMessage]] = Field(default_factory=list)
    bound_tools: list[Any] = Field(default_factory=list)

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        # Record the input the agent fed to the LLM (for assertion).
        # Only override the sync path — BaseChatModel._agenerate falls back to running
        # _generate in a thread, so this captures both sync and async invocations
        # without double-counting.
        self.received_inputs.append(list(messages))
        return super()._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def bind_tools(self, tools: list, **_kwargs: Any) -> "ScriptedFakeChatModel":  # type: ignore[override]
        self.bound_tools = list(tools)
        return self


class FakeCalculator(BaseTool):
    """Deterministic calculator tool — returns a string for any expression input."""

    name: str = "calculator"
    description: str = "Use this tool to evaluate a math expression. Input: expression (str)."

    def _run(self, expression: str = "0", **_kwargs: Any) -> str:
        # Avoid eval — return a deterministic string the test can match on.
        return f"computed({expression})"

    async def _arun(self, expression: str = "0", **_kwargs: Any) -> str:
        return self._run(expression)


class FakeFetcher(BaseTool):
    """Deterministic URL fetcher tool."""

    name: str = "fetch_url"
    description: str = "Fetch the content of a URL."

    def _run(self, url: str = "", **_kwargs: Any) -> str:
        return f"content of {url}"

    async def _arun(self, url: str = "", **_kwargs: Any) -> str:
        return self._run(url)


# ============================================================================
# Component test harness
# ============================================================================


def _make_component(
    *,
    llm: ScriptedFakeChatModel,
    tools: list[BaseTool] | None = None,
    chat_history: list | None = None,
    input_value: Any = "",
    max_iterations: int | None = None,
    handle_parsing_errors: bool = False,
    system_prompt: str = "You are a helpful assistant.",
) -> ToolCallingAgentComponent:
    component = ToolCallingAgentComponent()
    component._user_id = None
    component.cache = {}
    component._token_usage = None
    component._vertex = SimpleNamespace(graph=SimpleNamespace(session_id="test-session", flow_id=None, user_id=None))
    component._event_manager = None
    component.status = None
    component.send_message = AsyncMock(side_effect=_persisting_send)
    component._get_shared_callbacks = MagicMock(return_value=[])
    component.log = MagicMock()
    component.set(
        model="fake-model",
        system_prompt=system_prompt,
        handle_parsing_errors=handle_parsing_errors,
        verbose=False,
        max_iterations=max_iterations,
        api_key=None,
    )
    # Set tools and chat_history directly — `.set()` wraps list args in tuples
    # in some lfx Component code paths, breaking iteration over BaseTool instances.
    component.tools = tools or []
    component.chat_history = chat_history or []
    component.input_value = input_value
    # Force _get_llm to return the scripted fake.
    component._get_llm = MagicMock(return_value=llm)  # type: ignore[method-assign]
    return component


_send_call_counter: dict[str, int] = {"count": 0}


async def _persisting_send(message: Message, skip_db_update: bool = False) -> Message:  # noqa: ARG001
    """Mimic the production send_message: assigns an ID on first persist."""
    _send_call_counter["count"] += 1
    if _send_call_counter["count"] == 1:
        message.data["id"] = f"msg-{_send_call_counter['count']}"
    return message


@pytest.fixture(autouse=True)
def _reset_send_counter():
    _send_call_counter["count"] = 0


# ============================================================================
# Test cases — each one corresponds to a Smoke from MANUAL_TESTING_*.md
# ============================================================================


# ---- Smoke #5 — empty input + AI-tail history (the regression we caught) ----


@pytest.mark.asyncio
async def test_should_not_replay_tool_calls_when_input_is_empty_and_history_ends_with_ai_message() -> None:
    """Bug #1 regression at the integration level.

    With history ending in an AIMessage from a prior tool-using turn, an empty
    input must NOT cause the LLM to re-receive a malformed messages list (one
    ending with AIMessage). The safeguard must inject a HumanMessage continuation.
    """
    llm = ScriptedFakeChatModel(responses=[AIMessage(content="Anything else?")])
    history = [
        Data(text="Calculate 17 * 23", sender=MESSAGE_SENDER_USER),
        Data(text="The answer is 391.", sender=MESSAGE_SENDER_AI),
    ]
    component = _make_component(llm=llm, tools=[FakeCalculator()], chat_history=history, input_value="")

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)

    # The LLM was called exactly once (one model call, no tool replay).
    assert len(llm.received_inputs) == 1
    # The messages it received MUST end with a HumanMessage (the continuation prompt).
    last_message = llm.received_inputs[0][-1]
    assert isinstance(last_message, HumanMessage), (
        f"LLM received messages ending with {type(last_message).__name__} "
        f"(content={last_message.content!r}) — should be HumanMessage"
    )
    # No tool was invoked (final answer was returned directly).
    tool_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, ToolContent)]
    assert len(tool_blocks) == 0, "Empty input must not trigger tool calls"
    # The scripted final text reaches the user.
    assert result.text == "Anything else?"


# ---- Smoke #4 — chat memory respected ----


@pytest.mark.asyncio
async def test_should_pass_full_chat_history_to_llm_when_history_is_provided() -> None:
    """Smoke #4 contract: chat history is forwarded to the LLM as `messages`."""
    llm = ScriptedFakeChatModel(responses=[AIMessage(content="Your favorite color is purple.")])
    history = [
        Data(text="My favorite color is purple.", sender=MESSAGE_SENDER_USER),
        Data(text="Got it — purple is a great color.", sender=MESSAGE_SENDER_AI),
    ]
    component = _make_component(llm=llm, tools=[], chat_history=history, input_value="What is my favorite color?")

    graph = component.create_agent_runnable()
    await component.run_agent(graph)

    received = llm.received_inputs[0]
    # System prompt + 2 history items + 1 fresh input = at least 3 messages
    # (system might be merged into one slot depending on the create_agent shape).
    contents_seen = [_content_text(m) for m in received]
    assert any("My favorite color is purple." in c for c in contents_seen)
    assert any("Got it — purple is a great color." in c for c in contents_seen)
    assert any("What is my favorite color?" in c for c in contents_seen)
    # Fresh input must be the LAST human turn.
    last_human_idx = max(i for i, m in enumerate(received) if isinstance(m, HumanMessage))
    assert "What is my favorite color?" in _content_text(received[last_human_idx])


# ---- Smoke #6 — max_iterations enforces model call limit ----


@pytest.mark.asyncio
async def test_should_stop_after_max_iterations_model_calls_when_llm_keeps_emitting_tool_calls() -> None:
    """Smoke #6 contract: with max_iterations=2 and a model that always emits
    tool_calls, the agent halts after 2 model calls (does not loop forever).

    NOTE: max_iterations counts MODEL CALLS, not tool calls. Documented behavior.
    """
    # Always emit a tool call — would loop forever without the limit.
    looping_response = AIMessage(
        content="",
        tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": "loop"}],
    )
    llm = ScriptedFakeChatModel(responses=[looping_response, looping_response, looping_response])
    component = _make_component(
        llm=llm,
        tools=[FakeCalculator()],
        input_value="loop forever please",
        max_iterations=2,
    )

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)

    # Model was called at most 2 times (the run_limit).
    assert len(llm.received_inputs) <= 2, f"max_iterations=2 must cap LLM calls; got {len(llm.received_inputs)}"
    # Run terminated; result is a complete Message (no infinite spinner).
    assert result is not None
    assert result.properties.state in ("complete", "partial")  # both acceptable; not stuck


@pytest.mark.asyncio
async def test_should_make_unbounded_model_calls_when_max_iterations_is_none() -> None:
    """When max_iterations is unset (None), no ModelCallLimitMiddleware is wired
    and the agent terminates only when the LLM stops emitting tool calls.
    """
    llm = ScriptedFakeChatModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": "1"}]),
            AIMessage(content="Final answer."),
        ]
    )
    component = _make_component(llm=llm, tools=[FakeCalculator()], input_value="hi", max_iterations=None)

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)

    # 2 LLM calls — no artificial cap, terminated on its own.
    assert len(llm.received_inputs) == 2
    assert result.text == "Final answer."


# ---- Smoke #1/#2 — tool calling happy path ----


@pytest.mark.asyncio
async def test_should_render_tool_block_in_content_blocks_when_llm_emits_tool_call() -> None:
    """Smoke #1 contract: a single tool_call produces one ToolContent block in
    `content_blocks[0].contents`, with `name`, `tool_input`, `output` populated.
    """
    llm = ScriptedFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[{"name": "calculator", "args": {"expression": "2+2"}, "id": "tc-1"}],
            ),
            AIMessage(content="The answer is 4."),
        ]
    )
    component = _make_component(llm=llm, tools=[FakeCalculator()], input_value="What is 2+2?")

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)

    tool_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, ToolContent)]
    assert len(tool_blocks) == 1
    assert tool_blocks[0].name == "calculator"
    assert tool_blocks[0].tool_input == {"expression": "2+2"}
    assert "computed(2+2)" in str(tool_blocks[0].output)
    assert result.text == "The answer is 4."


@pytest.mark.asyncio
async def test_should_render_two_tool_blocks_when_llm_emits_parallel_tool_calls() -> None:
    """Smoke #2 contract: parallel tool calls in a single AIMessage produce
    multiple ToolContent blocks, all executed.
    """
    llm = ScriptedFakeChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {"name": "calculator", "args": {"expression": "17*23"}, "id": "a"},
                    {"name": "fetch_url", "args": {"url": "https://example.com"}, "id": "b"},
                ],
            ),
            AIMessage(content="17*23=391; example.com fetched."),
        ]
    )
    component = _make_component(
        llm=llm,
        tools=[FakeCalculator(), FakeFetcher()],
        input_value="run both",
    )

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)

    tool_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, ToolContent)]
    assert len(tool_blocks) == 2
    names = {b.name for b in tool_blocks}
    assert names == {"calculator", "fetch_url"}


# ---- Final-text rendering ----


@pytest.mark.asyncio
async def test_should_render_final_text_block_when_llm_returns_no_tool_calls() -> None:
    """When the LLM returns a single AIMessage with content (no tools), the
    final text shows up in `result.text` and a TextContent("Output") block is
    appended to content_blocks.
    """
    llm = ScriptedFakeChatModel(responses=[AIMessage(content="Hello, world.")])
    component = _make_component(llm=llm, tools=[], input_value="say hi")

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)

    assert result.text == "Hello, world."
    output_blocks = [
        c for c in result.content_blocks[0].contents if isinstance(c, TextContent) and c.header.get("title") == "Output"
    ]
    assert len(output_blocks) == 1


# ---- Multimodal contract (the part that IS testable without a real vision LLM) ----


@pytest.mark.asyncio
async def test_should_pass_multimodal_content_to_llm_when_input_message_has_list_content() -> None:
    """Multimodal smoke contract: when input_value is a Message whose
    to_lc_message() returns list-content (text + image_url), the LLM receives
    the SAME list-content unchanged.

    This was a regression risk: legacy code extracted images and pushed them
    to chat_history. New code passes them through.
    """
    llm = ScriptedFakeChatModel(responses=[AIMessage(content="An image was provided.")])
    multimodal = Message(text="describe", sender=MESSAGE_SENDER_USER)
    multimodal_payload = [
        {"type": "text", "text": "describe"},
        {"type": "image_url", "image_url": {"url": "https://example.invalid/x.png"}},
    ]

    from unittest.mock import patch

    component = _make_component(llm=llm, tools=[], input_value=multimodal)

    with patch.object(Message, "to_lc_message", return_value=HumanMessage(content=multimodal_payload)):
        graph = component.create_agent_runnable()
        await component.run_agent(graph)

    received = llm.received_inputs[0]
    last_human = next(m for m in reversed(received) if isinstance(m, HumanMessage))
    assert isinstance(last_human.content, list), (
        f"Multimodal payload was flattened: got {type(last_human.content).__name__}"
    )
    assert any(part.get("type") == "image_url" for part in last_human.content), (
        "image_url part missing from LLM input — flattened by mistake"
    )


# ---- Smoke #7 contract — WatsonX async path doesn't raise NotImplementedError ----


class ScriptedFakeWatsonxModel(ScriptedFakeChatModel):
    """Fake chat model whose class name contains 'watsonx' so `is_watsonx_model`
    detects it as a WatsonX provider — triggers the WatsonXAgentMiddleware path.
    """


@pytest.mark.asyncio
async def test_should_run_watsonx_agent_through_async_path_without_not_implemented_error() -> None:
    """Regression: when the WatsonX middleware is wired and the agent is invoked
    via `astream_events` (async), the middleware's `awrap_model_call` must be
    implemented — not just `wrap_model_call`. Otherwise the entire WatsonX flow
    blows up with `NotImplementedError` (production block, caught manually).
    """
    llm = ScriptedFakeWatsonxModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": "w"}]),
            AIMessage(content="2"),
        ]
    )
    component = _make_component(llm=llm, tools=[FakeCalculator()], input_value="add 1 and 1")

    graph = component.create_agent_runnable()
    result = await component.run_agent(graph)  # MUST NOT raise NotImplementedError

    # Tool ran successfully, agent finished.
    tool_blocks = [c for c in result.content_blocks[0].contents if isinstance(c, ToolContent)]
    assert len(tool_blocks) >= 1
    assert result.text == "2"


# ---- Tool execution ordering (state machine sanity) ----


@pytest.mark.asyncio
async def test_should_send_tool_messages_back_to_llm_on_next_call() -> None:
    """Verify the LangGraph loop: after the first AIMessage (with tool_calls)
    triggers tool execution, the SECOND model call must include ToolMessages
    in the `messages` list — that is the agent loop's contract.
    """
    llm = ScriptedFakeChatModel(
        responses=[
            AIMessage(content="", tool_calls=[{"name": "calculator", "args": {"expression": "1+1"}, "id": "x"}]),
            AIMessage(content="2"),
        ]
    )
    component = _make_component(llm=llm, tools=[FakeCalculator()], input_value="add")

    graph = component.create_agent_runnable()
    await component.run_agent(graph)

    assert len(llm.received_inputs) == 2
    second_call_messages = llm.received_inputs[1]
    tool_messages = [m for m in second_call_messages if isinstance(m, ToolMessage)]
    assert len(tool_messages) == 1, "Tool result must be threaded back to the LLM on the next call"
    assert "computed(1+1)" in str(tool_messages[0].content)


# ============================================================================
# Helpers
# ============================================================================


def _content_text(message: BaseMessage) -> str:
    content = message.content
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") for p in content if isinstance(p, dict) and p.get("type") == "text")
    return ""
