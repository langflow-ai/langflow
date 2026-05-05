"""Tests for WatsonXAgentMiddleware (replaces create_granite_agent under create_agent).

Slices S10-S12 of langchain_classic.AgentExecutor → langchain.agents.create_agent migration.

The middleware preserves three WatsonX platform-specific behaviors:
- S10: Dynamic tool_choice ('required' for first N model calls, then 'auto').
- S11: Truncate to a single tool call per turn.
- S12: Detect placeholder syntax in tool args and re-invoke with corrective message.
"""

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from lfx.components.langchain_utilities.ibm_granite_middleware import (
    DEFAULT_FORCED_ITERATIONS,
    WatsonXAgentMiddleware,
    build_watsonx_middleware,
)


class _FakeModelRequest:
    """Stand-in for `langchain.agents.middleware.types.ModelRequest` in tests.

    Implements the immutable `override(...)` contract: returns a NEW request with
    the given attributes replaced. The middleware MUST use this instead of mutating
    the original — direct attribute assignment is deprecated by langchain.
    """

    def __init__(self, *, state: Any, model: Any = None) -> None:
        self.state = state
        self.model = model

    def override(self, **overrides: Any) -> "_FakeModelRequest":
        new = _FakeModelRequest(state=self.state, model=self.model)
        for key, value in overrides.items():
            setattr(new, key, value)
        return new


def _llm_supporting_bind_tools() -> MagicMock:
    """Return a mock LLM whose bind_tools returns a tagged variant per tool_choice."""
    llm = MagicMock()

    def _bind_tools(tools, tool_choice="auto", **_kwargs):  # noqa: ARG001
        bound = MagicMock()
        bound.tool_choice = tool_choice
        return bound

    llm.bind_tools.side_effect = _bind_tools
    return llm


# ===== S10: dynamic tool_choice ===============================================


def test_should_force_required_tool_choice_for_first_iterations_when_model_is_watsonx() -> None:
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[], forced_iterations=2)

    assert middleware.select_tool_choice(num_steps=0) == "required"
    assert middleware.select_tool_choice(num_steps=1) == "required"


def test_should_relax_to_auto_tool_choice_after_forced_iterations() -> None:
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[], forced_iterations=2)

    assert middleware.select_tool_choice(num_steps=2) == "auto"
    assert middleware.select_tool_choice(num_steps=10) == "auto"


def test_should_use_default_forced_iterations_when_not_provided() -> None:
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[])

    assert middleware.select_tool_choice(num_steps=DEFAULT_FORCED_ITERATIONS - 1) == "required"
    assert middleware.select_tool_choice(num_steps=DEFAULT_FORCED_ITERATIONS) == "auto"


def test_should_raise_when_llm_lacks_bind_tools_support() -> None:
    bad_llm = SimpleNamespace()  # has no bind_tools attr

    with pytest.raises(ValueError, match="bind_tools"):
        WatsonXAgentMiddleware(llm=bad_llm, tools=[])


def test_should_bind_tools_for_both_required_and_auto_choices_at_construction_time() -> None:
    llm = _llm_supporting_bind_tools()
    tools = [MagicMock(name="t1")]

    WatsonXAgentMiddleware(llm=llm, tools=tools)

    bound_choices = [call.kwargs.get("tool_choice") for call in llm.bind_tools.call_args_list]
    assert "required" in bound_choices
    assert "auto" in bound_choices


# ===== S11: single tool call per turn =========================================


def test_should_truncate_to_single_tool_call_when_response_has_multiple() -> None:
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[])
    response = AIMessage(
        content="",
        tool_calls=[
            {"id": "1", "name": "calc", "args": {"x": 1}},
            {"id": "2", "name": "calc", "args": {"x": 2}},
            {"id": "3", "name": "calc", "args": {"x": 3}},
        ],
    )

    request = _FakeModelRequest(state={"messages": []}, model=middleware._llm_required)
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(request, handler)

    assert isinstance(result, AIMessage)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["id"] == "1"


def test_should_keep_response_unchanged_when_zero_or_one_tool_calls() -> None:
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[])
    response = AIMessage(content="", tool_calls=[{"id": "1", "name": "calc", "args": {"x": 1}}])
    request = _FakeModelRequest(state={"messages": []}, model=middleware._llm_required)
    handler = MagicMock(return_value=response)

    result = middleware.wrap_model_call(request, handler)

    assert len(result.tool_calls) == 1


# ===== S10 wiring: model swap based on step count =============================


def test_should_swap_model_to_required_variant_when_no_tool_messages_yet() -> None:
    """The handler must receive a NEW request whose model is the required variant —
    using `request.override(model=...)` (immutable), NOT mutating in place.
    """
    llm = _llm_supporting_bind_tools()
    middleware = WatsonXAgentMiddleware(llm=llm, tools=[], forced_iterations=2)
    request = _FakeModelRequest(state={"messages": [HumanMessage(content="q")]}, model=None)

    captured: list = []

    def handler(req):
        captured.append(req)
        return AIMessage(content="ok")

    middleware.wrap_model_call(request, handler)

    # Original request is NOT mutated.
    assert request.model is None
    # Handler received a NEW request with the required variant.
    assert captured[0].model is middleware._llm_required
    assert captured[0] is not request


def test_should_swap_model_to_auto_variant_after_forced_iterations() -> None:
    llm = _llm_supporting_bind_tools()
    middleware = WatsonXAgentMiddleware(llm=llm, tools=[], forced_iterations=2)
    state_with_two_tool_msgs = {
        "messages": [
            HumanMessage(content="q"),
            ToolMessage(content="r1", tool_call_id="a"),
            ToolMessage(content="r2", tool_call_id="b"),
        ]
    }
    request = _FakeModelRequest(state=state_with_two_tool_msgs, model=None)

    captured: list = []

    def handler(req):
        captured.append(req)
        return AIMessage(content="final")

    middleware.wrap_model_call(request, handler)

    assert request.model is None  # original untouched
    assert captured[0].model is middleware._llm_auto


def test_should_not_mutate_original_request_when_using_override() -> None:
    """Regression: `request.model = ...` is deprecated. The middleware MUST use
    `request.override(model=...)` which returns a new request, leaving the
    original unchanged. Direct mutation can break streaming sessions because the
    framework retains a reference to the original request.
    """
    llm = _llm_supporting_bind_tools()
    middleware = WatsonXAgentMiddleware(llm=llm, tools=[], forced_iterations=2)
    sentinel_model = object()
    request = _FakeModelRequest(state={"messages": []}, model=sentinel_model)
    handler = MagicMock(return_value=AIMessage(content="ok"))

    middleware.wrap_model_call(request, handler)

    # Original model attribute on the input request must remain the sentinel.
    assert request.model is sentinel_model


# ===== Factory ================================================================


def test_should_build_watsonx_middleware_via_factory() -> None:
    llm = _llm_supporting_bind_tools()

    middleware = build_watsonx_middleware(llm=llm, tools=[])

    assert isinstance(middleware, WatsonXAgentMiddleware)


# ===== Async path (awrap_model_call) — REGRESSION =============================


@pytest.mark.asyncio
async def test_should_support_async_invocation_via_awrap_model_call() -> None:
    """Regression: middleware MUST implement `awrap_model_call`.

    The sync-only implementation was a bug because `LCAgentComponent.run_agent`
    invokes the graph via `astream_events` (async path), which routes through
    `awrap_model_call`. A sync-only middleware raised
    `NotImplementedError: Asynchronous implementation of awrap_model_call is not
    available` in production, blocking the entire WatsonX agent flow (caught
    during manual Smoke #7).
    """
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[], forced_iterations=2)
    request = _FakeModelRequest(state={"messages": [HumanMessage(content="q")]}, model=None)
    captured: list = []

    async def handler(req):
        captured.append(req)
        return AIMessage(content="ok")

    response = await middleware.awrap_model_call(request, handler)

    assert isinstance(response, AIMessage)
    assert request.model is None  # original not mutated
    assert captured[0].model is middleware._llm_required


@pytest.mark.asyncio
async def test_should_truncate_to_single_tool_call_in_async_path_too() -> None:
    """Async path must apply the same single-tool-call truncation as sync."""
    from unittest.mock import AsyncMock

    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[])
    response = AIMessage(
        content="",
        tool_calls=[
            {"id": "1", "name": "calc", "args": {"x": 1}},
            {"id": "2", "name": "calc", "args": {"x": 2}},
        ],
    )
    request = _FakeModelRequest(state={"messages": []}, model=middleware._llm_required)
    handler = AsyncMock(return_value=response)

    result = await middleware.awrap_model_call(request, handler)

    assert len(result.tool_calls) == 1


@pytest.mark.asyncio
async def test_should_swap_to_auto_in_async_path_after_forced_iterations() -> None:
    """Async path uses the same step counting and tool_choice swap rule."""
    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[], forced_iterations=2)
    state_with_two_tool_msgs = {
        "messages": [
            HumanMessage(content="q"),
            ToolMessage(content="r1", tool_call_id="a"),
            ToolMessage(content="r2", tool_call_id="b"),
        ]
    }
    request = _FakeModelRequest(state=state_with_two_tool_msgs, model=None)
    captured: list = []

    async def handler(req):
        captured.append(req)
        return AIMessage(content="final")

    await middleware.awrap_model_call(request, handler)

    assert request.model is None  # original untouched
    assert captured[0].model is middleware._llm_auto


# ===== Placeholder re-invoke (S12) — REGRESSION ===============================


@pytest.mark.asyncio
async def test_should_use_ainvoke_when_placeholder_detected_in_async_path() -> None:
    """Regression: async path must NOT call sync `.invoke()` on the LLM.

    Bug: when the LLM emits tool args with placeholder syntax
    (`<result-from-...>`), the middleware re-invokes the LLM with a corrective
    message. The original implementation called `llm_auto.invoke(...)` (sync)
    from inside `awrap_model_call` (async), blocking the event loop and
    crashing async-only providers (langchain-ibm) with
    `RuntimeError: asyncio.run() cannot be called from a running event loop`.

    Expected: the async path uses `await llm_auto.ainvoke(...)`.
    """
    from unittest.mock import AsyncMock

    middleware = WatsonXAgentMiddleware(llm=_llm_supporting_bind_tools(), tools=[])

    corrected = AIMessage(content="actual values from previous results")
    # Replace mocked async/sync invocation paths so we can observe which one was used.
    middleware._llm_auto.invoke = MagicMock(return_value=corrected)
    middleware._llm_auto.ainvoke = AsyncMock(return_value=corrected)

    response_with_placeholder = AIMessage(
        content="",
        tool_calls=[{"id": "1", "name": "fetch", "args": {"url": "<result-from-search>"}}],
    )
    request = _FakeModelRequest(state={"messages": [HumanMessage(content="q")]}, model=None)

    async def handler(req):  # noqa: ARG001
        return response_with_placeholder

    result = await middleware.awrap_model_call(request, handler)

    middleware._llm_auto.ainvoke.assert_awaited_once()
    middleware._llm_auto.invoke.assert_not_called()
    assert result is corrected
