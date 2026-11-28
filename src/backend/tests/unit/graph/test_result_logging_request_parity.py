"""Authenticated request/event/persistence parity for deferred graph result logging."""

import ast
import copy
import inspect
import json
import os
import re
import textwrap
from time import perf_counter
from uuid import uuid4

import pytest
from langflow.services.database.models.flow.model import Flow
from langflow.services.database.models.message.model import MessageTable
from langflow.services.deps import session_scope
from lfx.graph import Graph
from lfx.graph.graph import base as graph_module
from sqlmodel import select

from tests.unit.build_utils import get_build_events


def eager_control():
    """Reproduce just the old f-string call in the otherwise identical task method."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(Graph._execute_tasks)))
    replaced = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == "Vertex %s, result: %s, object: %s"
        ):
            parts = []
            for prefix, value in zip(("Vertex ", ", result: ", ", object: "), node.args[1:], strict=True):
                parts.extend(
                    [ast.Constant(value=prefix), ast.FormattedValue(value=copy.deepcopy(value), conversion=-1)]
                )
            node.args = [ast.JoinedStr(values=parts)]
            replaced += 1
    assert replaced == 1
    tree.body.insert(0, ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0))
    namespace = dict(vars(graph_module))
    exec(compile(ast.fix_missing_locations(tree), "eager_result_logging_control", "exec"), namespace)  # noqa: S102
    return namespace["_execute_tasks"]


def normalize(value):
    """Mask generated identities, timestamps, and measured durations only."""
    volatile = {
        "id",
        "session_id",
        "session",
        "run_id",
        "graph_run_id",
        "job_id",
        "timestamp",
        "created_at",
        "updated_at",
        "elapsed_time",
        "duration",
        "timedelta",
        "build_duration",
    }
    if isinstance(value, dict):
        return {key: normalize(item) for key, item in value.items() if key not in volatile}
    if isinstance(value, list):
        return [normalize(item) for item in value]
    if isinstance(value, str):
        # Intermediate history vertices render IDs/timestamps inside tables,
        # not just under structured keys. The fixture's user text is fixed.
        value = re.sub(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", "<uuid>", value)
        return re.sub(
            r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?: UTC|Z|[+-]\d{2}:\d{2})?", "<timestamp>", value
        )
    return value


@pytest.mark.parametrize("endpoint", ["run", "build"])
async def test_authenticated_result_logging_response_events_and_persistence(
    client, created_api_key, logged_in_headers, json_memory_chatbot_no_llm, monkeypatch, endpoint
):
    """Compare actual run/build paths with eager logging, keeping auth, tracing and SQLite."""
    flow_id = uuid4()
    raw = json.loads(json_memory_chatbot_no_llm)
    async with session_scope() as session:
        session.add(Flow(id=flow_id, name="Logging parity", data=raw.get("data", raw), user_id=created_api_key.user_id))
    methods = {"base": eager_control(), "head": Graph._execute_tasks}
    records = []
    expected = None
    expected_messages = None
    pairs = int(os.environ.get("LANGFLOW_LOGGING_BENCHMARK_PAIRS", "2"))
    try:
        for pair in range(-1, pairs):
            for mode in ("base", "head") if pair % 2 else ("head", "base"):
                method = methods[mode]
                calls = 0

                async def counted(self, *args, _method=method, **kwargs):
                    """Prove whether this endpoint actually reaches the changed logging path."""
                    nonlocal calls
                    calls += 1
                    return await _method(self, *args, **kwargs)

                monkeypatch.setattr(Graph, "_execute_tasks", counted)
                session_id = str(uuid4())
                started = perf_counter()
                if endpoint == "run":
                    response = await client.post(
                        f"api/v1/run/{flow_id}",
                        json={
                            "input_value": "hello",
                            "input_type": "chat",
                            "output_type": "chat",
                            "session_id": session_id,
                        },
                        headers={"x-api-key": created_api_key.api_key},
                    )
                    assert response.status_code == 200, response.text
                    payload = normalize(response.json())
                else:
                    response = await client.post(
                        f"api/v1/build/{flow_id}/flow",
                        json={"inputs": {"input_value": "hello", "session": session_id}},
                        headers=logged_in_headers,
                    )
                    assert response.status_code == 200, response.text
                    stream = await get_build_events(client, response.json()["job_id"], logged_in_headers)
                    assert stream.status_code == 200, stream.text
                    payload = normalize([json.loads(line) for line in stream.text.splitlines() if line.strip()])
                    assert any(row.get("event") == "end" for row in payload)
                    assert not any(row.get("event") == "error" for row in payload)
                elapsed = (perf_counter() - started) * 1000
                async with session_scope() as session:
                    messages = (
                        await session.exec(
                            select(MessageTable)
                            .where(MessageTable.session_id == session_id)
                            .order_by(MessageTable.sender)
                        )
                    ).all()
                    stored = normalize([message.model_dump(mode="json") for message in messages])
                assert stored
                if expected is None:
                    expected, expected_messages = payload, stored
                assert payload == expected
                assert stored == expected_messages
                records.append({"pair": pair, "mode": mode, "ms": elapsed, "task_method_calls": calls})
        if endpoint == "run":
            assert all(record["task_method_calls"] > 0 for record in records)
        print(json.dumps({"logging_request_samples": {"endpoint": endpoint, "records": records}}))  # noqa: T201
    finally:
        monkeypatch.setattr(Graph, "_execute_tasks", methods["head"])
        async with session_scope() as session:
            flow = await session.get(Flow, flow_id)
            if flow:
                await session.delete(flow)
