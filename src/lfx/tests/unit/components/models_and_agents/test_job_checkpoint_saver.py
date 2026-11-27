"""LE-1447 Slice 2: durable agent checkpoint saver round-trip.

A scripted tool-calling model requests a gated tool (pause), the paused thread is
serialized into a plain blob store via msgpack→base64→JSON, a FRESH saver is rebuilt
from that blob alone, and `Command(resume=approve)` runs the gated tool to completion.
No mocks of the serializer — the `__interrupt__` write is non-JSON and must survive.
"""

from __future__ import annotations

import asyncio
import json
import sys

import pytest
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.tools import tool
from langgraph.checkpoint.base import empty_checkpoint
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


def _store(*, delayed=False):
    blobs: dict[tuple[str, str], str] = {}

    async def save_blob(job_id: str, kind: str, blob: str) -> None:
        if delayed:
            await asyncio.sleep(0.001)
        blobs[(job_id, kind)] = blob

    async def load_blob(job_id: str, kind: str) -> str | None:
        if delayed:
            await asyncio.sleep(0.001)
        return blobs.get((job_id, kind))

    return blobs, save_blob, load_blob


def _agent(saver, tools=None):
    return create_agent(
        model=ScriptedModel(),
        tools=[transfer_money] if tools is None else tools,
        system_prompt="Use the tool.",
        middleware=[HumanInTheLoopMiddleware(interrupt_on={"transfer_money": True})],
        checkpointer=saver,
    )


# langgraph's interrupt() reads get_config(), which is only populated inside the node when langgraph
# runs it via asyncio.create_task(context=...) — gated on ASYNCIO_ACCEPTS_CONTEXT (Python >= 3.11).
# On 3.10 the config ContextVar is never set, so any HITL interrupt raises "Called get_config outside
# of a runnable context" (confirmed on langgraph 1.1.10 and 1.2.6). The durable-saver round trip needs
# a real interrupt, so it can only run on 3.11+; the blob serde itself is exercised version-agnostically
# by test_durable_saver_async_only.
@pytest.mark.skipif(
    sys.version_info < (3, 11),
    reason="langgraph HITL interrupt() needs asyncio create_task context= (Python 3.11+)",
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


@pytest.mark.asyncio
@pytest.mark.parametrize("with_parent", [False, True])
async def test_writes_before_checkpoint_are_restored_by_fresh_saver(with_parent):
    blobs, save_blob, load_blob = _store()
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    config = {"configurable": {"thread_id": "job-1", "checkpoint_ns": ""}}
    if with_parent:
        config = await saver.aput(config, empty_checkpoint(), {"source": "input", "step": -1}, {})
        await saver.aput_writes(config, [("__interrupt__", "old-approval")], "old-task")
    checkpoint = empty_checkpoint()
    target = {"configurable": {**config["configurable"], "checkpoint_id": checkpoint["id"]}}
    await saver.aput_writes(target, [("__interrupt__", "new-approval")], "task-1")
    # Rebuild before the checkpoint arrives: future writes must be durable too.
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    await saver.aput(config, checkpoint, {"source": "loop", "step": 0}, {})
    restored = await JobCheckpointSaver("job-1", save_blob, load_blob).aget_tuple(target)
    assert restored is not None
    assert restored.pending_writes == [("task-1", "__interrupt__", "new-approval")]
    assert ("job-1", "agent") in blobs


@pytest.mark.asyncio
async def test_writes_are_scoped_to_target_checkpoint_and_retired():
    _blobs, save_blob, load_blob = _store()
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    config = {"configurable": {"thread_id": "job-1", "checkpoint_ns": ""}}
    first, second, third = empty_checkpoint(), empty_checkpoint(), empty_checkpoint()
    first_config = await saver.aput(config, first, {"source": "input", "step": -1}, {})
    second_config = {"configurable": {**first_config["configurable"], "checkpoint_id": second["id"]}}
    third_config = {"configurable": {**first_config["configurable"], "checkpoint_id": third["id"]}}
    await saver.aput_writes(second_config, [("__interrupt__", "second-approval")], "task-2")
    await saver.aput_writes(third_config, [("__interrupt__", "third-approval")], "task-3")
    await saver.aput(first_config, second, {"source": "loop", "step": 0}, {})
    # A late write to an already superseded checkpoint must not contaminate the current one.
    await saver.aput_writes(first_config, [("__interrupt__", "late-old-approval")], "old-task")
    current = await saver.aget_tuple(second_config)
    assert current.pending_writes == [("task-2", "__interrupt__", "second-approval")]
    await saver.aput(second_config, third, {"source": "loop", "step": 1}, {})
    latest = await saver.aget_tuple(third_config)
    assert latest.pending_writes == [("task-3", "__interrupt__", "third-approval")]


@pytest.mark.asyncio
async def test_checkpoint_advances_do_not_retain_historical_write_payloads():
    blobs, save_blob, load_blob = _store()
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    config = {"configurable": {"thread_id": "job-1", "checkpoint_ns": ""}}
    first_size = None
    for step in range(50):
        checkpoint = empty_checkpoint()
        target = {"configurable": {**config["configurable"], "checkpoint_id": checkpoint["id"]}}
        await saver.aput_writes(target, [("__interrupt__", "x" * 100)], "task-1")
        config = await saver.aput(config, checkpoint, {"source": "loop", "step": step}, {})
        latest = await saver.aget_tuple(config)
        assert latest.pending_writes == [("task-1", "__interrupt__", "x" * 100)]
        size = len(blobs[("job-1", "agent")])
        first_size = size if first_size is None else first_size
        assert size <= first_size + 256


@pytest.mark.asyncio
async def test_legacy_blob_and_multiple_writes_for_same_checkpoint():
    blobs, save_blob, load_blob = _store()
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    config = await saver.aput(
        {"configurable": {"thread_id": "job-1"}}, empty_checkpoint(), {"source": "input", "step": -1}, {}
    )
    await saver.aput_writes(config, [("__interrupt__", "legacy-approval")], "task-1")
    legacy = json.loads(blobs[("job-1", "agent")])
    legacy.pop("future_writes", None)
    blobs[("job-1", "agent")] = json.dumps(legacy)
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    restored = await saver.aget_tuple(config)
    assert restored.pending_writes == [("task-1", "__interrupt__", "legacy-approval")]
    await saver.aput_writes(config, [("channel", "another-write")], "task-2")
    restored = await saver.aget_tuple(config)
    assert restored.pending_writes == [
        ("task-1", "__interrupt__", "legacy-approval"),
        ("task-2", "channel", "another-write"),
    ]
    await saver.aput(config, restored.checkpoint, restored.metadata, {})
    repeated = await saver.aget_tuple(config)
    assert repeated.pending_writes == restored.pending_writes


@pytest.mark.skipif(sys.version_info < (3, 11), reason="langgraph interrupt() requires Python 3.11+")
@pytest.mark.asyncio
@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_delayed_store_restores_interrupt_and_honors_decision(decision):
    _blobs, save_blob, load_blob = _store(delayed=True)
    executed = []

    @tool("transfer_money")
    def tracked_transfer(amount: int) -> str:
        """Record a synthetic tool execution."""
        executed.append(amount)
        return f"transferred {amount}"

    config = {"configurable": {"thread_id": "job-1"}}
    saver = JobCheckpointSaver("job-1", save_blob, load_blob)
    async for _ in _agent(saver, [tracked_transfer]).astream_events(
        {"messages": [("user", "send 200")]}, version="v2", config=config
    ):
        pass
    assert executed == []
    agent = _agent(JobCheckpointSaver("job-1", save_blob, load_blob), [tracked_transfer])
    pending = await agent.aget_state(config)
    assert pending.interrupts
    async for _ in agent.astream_events(
        Command(resume={"decisions": [{"type": decision}]}), version="v2", config=config
    ):
        pass
    assert executed == ([200] if decision == "approve" else [])
    assert not (await agent.aget_state(config)).interrupts
