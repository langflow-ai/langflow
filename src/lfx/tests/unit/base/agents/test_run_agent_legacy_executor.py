"""End-to-end integration test for the AgentExecutor fallback in `run_agent`.

The unit-level dispatch is covered by `test_legacy_agent_executor_fallback.py`.
This test drives the FULL `run_agent` path with a fake `AgentExecutor`, proving
that:

- The runnable receives `{"input": str}` (not `{"messages": [...]}`)
- `astream_events` is invoked and consumed without `KeyError`
- A `Message` is produced

Why this matters: PR #12982 reviewer (erichare) flagged that the previous
implementation always built `{"messages": [...]}` regardless of runnable type,
which would crash legacy components at runtime. This test pins the regression.
"""

from unittest.mock import MagicMock

import pytest
from langchain_classic.agents import AgentExecutor
from lfx.base.agents.agent import LCAgentComponent
from lfx.schema.message import Message


class _ConcreteLegacyAgent(LCAgentComponent):
    """Concrete subclass that exposes the abstract methods so the class is instantiable."""

    def build_agent(self):  # pragma: no cover - not exercised in this test
        raise NotImplementedError

    def create_agent_runnable(self):  # pragma: no cover - not exercised in this test
        raise NotImplementedError


@pytest.mark.asyncio
async def test_should_feed_input_dict_to_legacy_agent_executor_when_run_agent_invoked() -> None:
    """`run_agent` must give an `AgentExecutor` `{"input": str}` shape, not `{"messages": [...]}`."""
    captured: dict = {}

    async def _fake_astream(input_, **_kwargs):
        captured["input"] = input_
        if False:  # async generator that yields nothing
            yield {}

    executor = MagicMock(spec=AgentExecutor)
    executor.astream_events = _fake_astream

    async def _send(*_args, **kwargs):
        return kwargs.get("message")

    component = _ConcreteLegacyAgent()
    component._user_id = None
    component.input_value = Message(text="What is the largest table?")
    component.send_message = _send
    component._event_manager = None

    result = await component.run_agent(executor)

    assert isinstance(result, Message)
    assert "input" in captured["input"], (
        f"AgentExecutor MUST receive `input` key (legacy shape), got keys={list(captured['input'].keys())!r}"
    )
    assert "messages" not in captured["input"], (
        "AgentExecutor MUST NOT receive `messages` key (modern shape) — that is the reviewer's blocker"
    )
    assert captured["input"]["input"] == "What is the largest table?"
