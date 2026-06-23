"""LE-1447 Slice 2: durable agent checkpoint saver round-trip.

A scripted tool-calling model requests a gated tool (pause), the paused thread is
serialized into a plain blob store via msgpack→base64→JSON, a FRESH saver is rebuilt
from that blob alone, and `Command(resume=approve)` runs the gated tool to completion.
No mocks of the serializer — the `__interrupt__` write is non-JSON and must survive.
"""

from __future__ import annotations

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.types import Command
from lfx.components.models_and_agents.agent_helpers.job_checkpoint_saver import (
    JobCheckpointSaver,
)


@tool
def transfer_money(amount: int) -> str:
    """Transfer money (gated tool)."""
    return f"transferred {amount}"


class ScriptedModel(BaseChatModel):
    """Request the gated tool until a tool result exists, then answer."""

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):  # noqa: ARG002
        answered = any(isinstance(m, ToolMessage) for m in messages)
        msg = (
            AIMessage(content="Done — transferred.")
            if answered
            else AIMessage(
                content="",
                tool_calls=[{"name": "transfer_money", "args": {"amount": 200}, "id": "call_1"}],
            )
        )
        return ChatResult(generations=[ChatGeneration(message=msg)])


def _store():
    blobs: dict[tuple[str, str], str] = {}

    async def save_blob(job_id: str, kind: str, blob: str) -> None:
        blobs[(job_id, kind)] = blob

    async def load_blob(job_id: str, kind: str) -> str | None:
        return blobs.get((job_id, kind))

    return blobs, save_blob, load_blob


def _agent(saver):
    return create_agent(
        model=ScriptedModel(),
        tools=[transfer_money],
        system_prompt="Use the tool.",
        middleware=[HumanInTheLoopMiddleware(interrupt_on={"transfer_money": True})],
        checkpointer=saver,
    )


@pytest.mark.asyncio
async def test_durable_saver_round_trip_pauses_persists_and_resumes() -> None:
    blobs, save_blob, load_blob = _store()
    config = {"configurable": {"thread_id": "job-1"}}

    # Run 1: pauses at the gated tool; the paused thread is persisted to the blob store.
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    async for _ in _agent(saver).astream_events({"messages": [("user", "send 200")]}, version="v2", config=config):
        pass

    assert ("job-1", "agent") in blobs, "paused thread was not persisted"

    # Rebuild a FRESH saver from the stored blob alone (simulates a restart).
    saver2 = JobCheckpointSaver("job-1", save_blob, load_blob)
    restored = await saver2.aget_tuple(config)
    assert restored is not None
    assert any(channel == "__interrupt__" for _task, channel, _value in restored.pending_writes)

    # Resume approve on the rebuilt thread → the gated tool runs and the run completes.
    agent2 = _agent(saver2)
    async for _ in agent2.astream_events(
        Command(resume={"decisions": [{"type": "approve"}]}), version="v2", config=config
    ):
        pass

    final = await agent2.aget_state(config)
    messages = final.values.get("messages", [])
    assert any(isinstance(m, ToolMessage) and "transferred 200" in m.content for m in messages)
    assert any(isinstance(m, AIMessage) and "Done" in m.content for m in messages)
    assert not final.interrupts


@pytest.mark.asyncio
async def test_durable_saver_async_only() -> None:
    _blobs, save_blob, load_blob = _store()
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    with pytest.raises(NotImplementedError):
        saver.get_tuple({"configurable": {"thread_id": "job-1"}})
