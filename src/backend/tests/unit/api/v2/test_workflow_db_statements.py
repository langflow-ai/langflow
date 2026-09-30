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
from dataclasses import dataclass, field
from itertools import pairwise
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.deps import get_db_service
from lfx.services.deps import session_scope
from sqlalchemy import event

if TYPE_CHECKING:
    from httpx import AsyncClient

_TABLE_RE = re.compile(
    r'^\s*(?:(UPDATE)|(SELECT|INSERT|DELETE)\b.*?\b(?:FROM|INTO))\s+"?(\w+)"?', re.IGNORECASE | re.DOTALL
)


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
        recorder.statements.append(_classify(statement))

    def on_checkout(dbapi_connection, connection_record, connection_proxy):  # noqa: ARG001
        recorder.checkouts += 1

    event.listen(sync_engine, "before_cursor_execute", on_execute)
    event.listen(sync_engine.pool, "checkout", on_checkout)
    try:
        yield recorder
    finally:
        event.remove(sync_engine, "before_cursor_execute", on_execute)
        event.remove(sync_engine.pool, "checkout", on_checkout)


async def _settle(recorder: _Recorder) -> None:
    """Wait for fire-and-forget work (the memory-base hook) to finish its statements."""
    seen = -1
    for _ in range(50):
        if len(recorder.statements) == seen:
            return
        seen = len(recorder.statements)
        await asyncio.sleep(0.05)


@pytest.fixture
def serving_settings(client, monkeypatch):  # noqa: ARG001
    """Match the serving deployment the traces came from.

    Transaction and vertex-build storage and API-key usage tracking are off
    there; each adds its own writes per run that are not what this test is about.
    """
    from langflow.services.deps import get_settings_service

    settings = get_settings_service().settings
    monkeypatch.setattr(settings, "transactions_storage_enabled", False)
    monkeypatch.setattr(settings, "vertex_builds_storage_enabled", False)
    monkeypatch.setattr(settings, "disable_track_apikey_usage", True)


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
    body = {"flow_id": str(flow_id), "input_value": "hello", "mode": mode, "session_id": session_id}
    response = await client.post("api/v2/workflows", json=body, headers={"x-api-key": api_key})
    assert response.status_code == 200, response.text
    if mode == "sync":
        assert response.json()["status"] == "completed", response.text


async def _measure(client: AsyncClient, api_key: str, flow_id, mode: str) -> _Recorder:
    session_id = f"db-round-trips-{mode}"
    # Warm up once so one-off work (first flow load, lazy setup) is not counted.
    await _run(client, api_key, flow_id, mode, session_id)
    await asyncio.sleep(0.2)
    with _record_db_round_trips() as recorder:
        await _run(client, api_key, flow_id, mode, session_id)
        await _settle(recorder)
    print(f"\n{mode}: {len(recorder.statements)} statements, {recorder.checkouts} checkouts")  # noqa: T201
    for statement in recorder.statements:
        print(f"  {statement}")  # noqa: T201
    return recorder


# Statements and pool checkouts for one sync run, per flow. Update these on
# purpose: a new round trip on this path costs every workflow run.
_SYNC_ROUND_TRIPS = {
    "memory_chatbot": (9, 8),
    "simple_chat": (10, 8),
}


def _follows(statements: list[str], first: str, then: str) -> bool:
    return any(a == first and b == then for a, b in pairwise(statements))


@pytest.mark.parametrize("mode", ["sync", "stream"])
@pytest.mark.usefixtures("serving_settings")
async def test_run_db_round_trips(client: AsyncClient, created_api_key, chat_flow, mode, request):
    recorder = await _measure(client, created_api_key.api_key, chat_flow, mode)
    statements = recorder.statements

    # A job status change returns the row it wrote instead of reading it back.
    assert not _follows(statements, "UPDATE job", "SELECT job"), statements

    if mode == "sync":
        # The sync job row is created IN_PROGRESS and written once more when it ends.
        assert [s for s in statements if s.endswith(" job")] == ["INSERT job", "UPDATE job"], statements
        flow_name = request.node.callspec.params["chat_flow"]
        assert (len(statements), recorder.checkouts) == _SYNC_ROUND_TRIPS[flow_name], statements
