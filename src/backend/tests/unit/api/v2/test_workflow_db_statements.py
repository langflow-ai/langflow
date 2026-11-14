"""Database round trips per v2 workflow run.

Counts the SQL statements and connection-pool checkouts that one sync and one
stream run issue, so a change that adds a round trip to the per-run path shows
up here instead of only in production traces. The flow is the no-LLM memory
chatbot (ChatInput -> Memory -> Prompt -> ChatOutput): it stores the input and
the output message and reads the session history, like a chat flow does.
"""

from __future__ import annotations

import asyncio
import json
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.database.models.api_key.crud import hash_api_key
from langflow.services.database.models.api_key.model import ApiKey
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_db_service, get_queue_service, get_task_service
from lfx.services.deps import session_scope
from sqlalchemy import event, text

if TYPE_CHECKING:
    from httpx import AsyncClient

_TABLE_RE = re.compile(
    r'^\s*(?:(UPDATE)|(SELECT|INSERT|DELETE)\b.*?\b(?:FROM|INTO))\s+"?(\w+)"?', re.IGNORECASE | re.DOTALL
)
_MEASURING_RUN = ContextVar("measuring_workflow_round_trips", default=False)


def _classify(statement: str) -> str:
    match = _TABLE_RE.match(statement)
    if match is None:
        return statement.split(None, 1)[0].upper()
    verb = match.group(1) or match.group(2)
    return f"{verb.upper()} {match.group(3).lower()}"


@dataclass
class _Recorder:
    statements: list[str] = field(default_factory=list)
    checkouts: int = 0


@contextmanager
def _record_db_round_trips():
    sync_engine = get_db_service().engine.sync_engine
    recorder = _Recorder()

    def on_execute(conn, cursor, statement, parameters, context, executemany):  # noqa: ARG001
        if _MEASURING_RUN.get():
            recorder.statements.append(_classify(statement))

    def on_checkout(dbapi_connection, connection_record, connection_proxy):  # noqa: ARG001
        if _MEASURING_RUN.get():
            recorder.checkouts += 1

    event.listen(sync_engine, "before_cursor_execute", on_execute)
    event.listen(sync_engine.pool, "checkout", on_checkout)
    # Request tasks and their output hooks inherit this context. Independent
    # lifespan pollers use the same engine but are not part of a workflow run.
    token = _MEASURING_RUN.set(True)
    try:
        yield recorder
    finally:
        _MEASURING_RUN.reset(token)
        event.remove(sync_engine, "before_cursor_execute", on_execute)
        event.remove(sync_engine.pool, "checkout", on_checkout)


def _local_tasks() -> set[asyncio.Task]:
    """Snapshot the real local task handles, including completed output hooks."""
    assert not get_task_service().use_celery, "Round-trip tests require the local task backend"
    # The queue exposes lookup by job ID, but no public task enumeration API.
    return {row[2] for row in get_queue_service()._queues.values() if row[2] is not None}


async def _await_run_tasks(before: set[asyncio.Task]) -> None:
    """Join this run's hook tasks and their children before ending SQL recording."""
    joined: set[asyncio.Task] = set()

    async def drain() -> None:
        while tasks := _local_tasks() - before - joined:
            # Awaiting the handles propagates task failures as well as waiting
            # through idle periods before the hook issues its first statement.
            await asyncio.gather(*tasks)
            joined.update(tasks)

    await asyncio.wait_for(drain(), timeout=10)
    assert joined, "Expected a tracked memory-base output hook"


@pytest.fixture
async def serving_settings(client, monkeypatch, created_api_key):  # noqa: ARG001
    """Match the serving deployment the traces came from.

    Transaction and vertex-build storage and API-key usage tracking are off
    there; each adds its own writes per run that are not what this test is about.
    """
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "transactions_storage_enabled", False)
    monkeypatch.setattr(settings, "vertex_builds_storage_enabled", False)
    monkeypatch.setattr(settings, "disable_track_apikey_usage", True)
    # Preserve the trusted deployment's original code policy and measured execution path.
    monkeypatch.setattr(settings, "custom_component_admin_only", False)
    # Production keys are indexed at creation. Disabled tracking cannot backfill
    # the legacy test fixture during warmup, so seed that index before measuring.
    async with session_scope() as session:
        api_key = await session.get(ApiKey, created_api_key.id)
        assert api_key is not None
        api_key.api_key_hash = hash_api_key(created_api_key.api_key)


_SIMPLE_CHAT = Path(__file__).parents[5] / "lfx" / "tests" / "data" / "simple_chat_no_llm.json"


@pytest.fixture(params=["memory_chatbot", "simple_chat"])
async def chat_flow(request, created_api_key, json_memory_chatbot_no_llm):
    """A no-LLM chat flow owned by the API-key user.

    ``memory_chatbot`` (ChatInput -> Memory -> Prompt -> ChatOutput) stores two
    new messages and reads the session history. ``simple_chat`` (ChatInput ->
    ChatOutput) hands the stored input message, id included, to ChatOutput, so
    it covers the update-an-existing-message path an Agent's reply also takes.
    """
    text = json_memory_chatbot_no_llm if request.param == "memory_chatbot" else _SIMPLE_CHAT.read_text("utf-8")
    raw = json.loads(text)
    flow_id = uuid4()
    async with session_scope() as session:
        session.add(
            Flow(
                id=flow_id,
                name=f"DB round-trip flow {request.param}",
                data=raw.get("data", raw),
                user_id=created_api_key.user_id,
            )
        )
    yield flow_id
    async with session_scope() as session:
        flow = await session.get(Flow, flow_id)
        if flow:
            await session.delete(flow)


async def _run(client: AsyncClient, api_key: str, flow_id, mode: str, session_id: str) -> None:
    before = _local_tasks()
    body = {"flow_id": str(flow_id), "input_value": "hello", "mode": mode, "session_id": session_id}
    response = await client.post("api/v2/workflows", json=body, headers={"x-api-key": api_key})
    assert response.status_code == 200, response.text
    if mode == "sync":
        assert response.json()["status"] == "completed", response.text
    else:
        assert response.headers["content-type"].startswith("text/event-stream"), response.text
        events = [
            json.loads(line.removeprefix("data:").strip())
            for line in response.text.splitlines()
            if line.startswith("data:")
        ]
        assert events, "Stream had no JSON event payloads"
        assert not any(item.get("event") == "error" for item in events), events
        assert events[-1].get("event") == "end", events
        outputs = [item["data"] for item in events if item.get("event") == "output"]
        assert outputs, "Stream ended without a terminal component output"
        assert all(output["status"] == "completed" and output["type"] != "error" for output in outputs), outputs
        assert all(isinstance(output.get("content"), str) and output["content"].strip() for output in outputs), outputs
    await _await_run_tasks(before)


async def _measure(client: AsyncClient, api_key: str, flow_id, mode: str) -> _Recorder:
    session_id = f"db-round-trips-{mode}"
    # Warm up once so one-off work (first flow load, lazy setup) is not counted.
    await _run(client, api_key, flow_id, mode, session_id)
    with _record_db_round_trips() as recorder:
        await _run(client, api_key, flow_id, mode, session_id)
    print(f"\n{mode}: {len(recorder.statements)} statements, {recorder.checkouts} checkouts")  # noqa: T201
    for statement in recorder.statements:
        print(f"  {statement}")  # noqa: T201
    return recorder


# Statements and pool checkouts for one run, per flow and mode. Update these
# on purpose: a new round trip on this path costs every workflow run. The user
# lookup prevents a legacy flow storage namespace from colliding with a user ID.
# Each message write also rechecks the execution user's active status in its existing session.
_ROUND_TRIPS = {
    "memory_chatbot": {"sync": (12, 9), "stream": (15, 12)},
    "simple_chat": {"sync": (13, 9), "stream": (16, 12)},
}
# Admission reads the originating key inside the existing job transaction.
# Execution reloads key, owner, and flow together in one additional checkout.
# Shared maintenance is checked at request entry, hook admission, and hook start.
# Each check uses a fresh read-only session so pods see each other's changes.

# Streaming also reloads the job's persisted credential provenance after the
# conditional start; sync reuses the row it created IN_PROGRESS.
_JOB_KEY_AUTHORIZATION_ROUND_TRIPS = {"sync": (4, 1), "stream": (5, 2)}

# Shared maintenance is checked at request entry, hook admission, and hook start.
# Each check uses a fresh read-only session so pods see each other's changes.
_MAINTENANCE_ROUND_TRIPS = (3, 3)


def _assert_round_trips(recorder: _Recorder, expected: tuple[int, int], *, maintenance_reads: int) -> None:
    # Every admission reads the shared flag through its own read-only session.
    # Keep this exact cost visible without relaxing the existing execution budget.
    assert recorder.statements.count("SELECT maintenance_state") == maintenance_reads, recorder.statements
    assert (len(recorder.statements), recorder.checkouts) == (
        expected[0] + maintenance_reads,
        expected[1] + maintenance_reads,
    ), recorder.statements


@pytest.mark.parametrize("mode", ["sync", "stream"])
@pytest.mark.usefixtures("serving_settings")
async def test_run_db_round_trips(client: AsyncClient, created_api_key, chat_flow, mode, request):
    recorder = await _measure(client, created_api_key.api_key, chat_flow, mode)
    statements = recorder.statements
    # One read each for request authentication, legacy storage isolation, and job credential
    # revalidation, plus one lifecycle check for each of the two message writes.
    assert statements.count("SELECT user") == 5, statements

    if mode == "sync":
        # The sync job row is created IN_PROGRESS and written once more when it ends.
        expected_job_statements = ["INSERT job", "UPDATE job"]
    else:
        # The first read checks for an existing job. The second reloads credential
        # provenance after the conditional start, rather than reading back status.
        expected_job_statements = ["SELECT job", "INSERT job", "UPDATE job", "SELECT job", "UPDATE job"]
    assert [s for s in statements if s.endswith(" job")] == expected_job_statements, statements
    flow_name = request.node.callspec.params["chat_flow"]
    base_statements, base_checkouts = _ROUND_TRIPS[flow_name][mode]
    key_statements, key_checkouts = _JOB_KEY_AUTHORIZATION_ROUND_TRIPS[mode]
    # One HTTP admission, then submission and start of the memory-base output
    # hook. The queued start must recheck a freeze set after submission.
    _assert_round_trips(
        recorder,
        (base_statements + key_statements, base_checkouts + key_checkouts),
        maintenance_reads=3,
    )


@pytest.mark.usefixtures("client")
async def test_round_trip_recording_excludes_background_polling():
    poll = asyncio.Event()

    async def background_poll():
        await poll.wait()
        async with session_scope() as session:
            await session.execute(text("SELECT 2"))

    task = asyncio.create_task(background_poll())
    try:
        with _record_db_round_trips() as recorder:
            poll.set()
            await task
            async with session_scope() as session:
                await session.execute(text("SELECT 1"))
        assert recorder.statements == ["SELECT"]
        assert recorder.checkouts == 1
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.usefixtures("client")
async def test_run_task_wait_includes_delayed_child_sql():
    """Keep recording until a gated hook and the task it spawns both finish."""
    hook_started = asyncio.Event()
    release_hook = asyncio.Event()
    child_started = asyncio.Event()
    release_child = asyncio.Event()

    async def child() -> None:
        child_started.set()
        await release_child.wait()
        async with session_scope() as session:
            await session.execute(text("SELECT 2"))

    async def hook() -> None:
        hook_started.set()
        await release_hook.wait()
        async with session_scope() as session:
            await session.execute(text("SELECT 1"))
        await get_task_service().fire_and_forget_task(child)

    async def record_hook() -> _Recorder:
        before = _local_tasks()
        with _record_db_round_trips() as recorder:
            await get_task_service().fire_and_forget_task(hook)
            await _await_run_tasks(before)
        return recorder

    measurement = asyncio.create_task(record_hook())
    try:
        await asyncio.wait_for(hook_started.wait(), timeout=10)
        assert not measurement.done(), "Recording ended while the hook was blocked"
        release_hook.set()
        await asyncio.wait_for(child_started.wait(), timeout=10)
        assert not measurement.done(), "Recording ended while the child was blocked"
        release_child.set()
        recorder = await asyncio.wait_for(measurement, timeout=10)
    finally:
        release_hook.set()
        release_child.set()
        if not measurement.done():
            measurement.cancel()
        await asyncio.gather(measurement, return_exceptions=True)

    assert [statement for statement in recorder.statements if statement != "SELECT maintenance_state"] == [
        "SELECT",
        "SELECT",
    ]
    # Both the parent hook and its child check admission when submitted and
    # again when the queue starts them. Their own two statements remain counted.
    _assert_round_trips(recorder, (2, 2), maintenance_reads=4)
