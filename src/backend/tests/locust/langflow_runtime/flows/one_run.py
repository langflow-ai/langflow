"""In-process one-run validation for V1 performance-suite fixtures.

Executes fixture graphs via ``run_graph_internal`` and checks expected-output
rules plus subsystem side effects (message store, storage upload markers).

Flows that require live HTTP protocols (webhook SSE), HITL suspend/resume,
background job queue admission, provisioned KB directories, or real LLM keys are
skipped here and covered by ``tests/locust/tests/integration/``.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from lfx.graph import Graph
from lfx.memory import aget_messages
from lfx.processing.process import run_graph_internal
from lfx.schema.schema import InputValueRequest

from tests.locust.langflow_runtime.datasets.storage_payload import bounded_payload_text
from tests.locust.langflow_runtime.flows.defaults import DEFAULT_CHAT_INPUT, FLOWS_DIR

FIXTURE_INDEX_PATH = FLOWS_DIR / "fixture_index.json"

# Isolators that can prove their primary subsystem without HTTP protocol clients,
# provisioned KBs, or outbound API keys.
IN_PROCESS_ONE_RUN_IDS = frozenset(
    {
        "perf_passthrough",
        "perf_cpu_graph",
        "perf_multiproc_churn",
        "perf_queue_short",  # proves sleep work; queue admission is integration-only
        "MemoryChatbotNoLLM",
        # perf_payload_echo needs a real user_id for SaveToFile → covered in integration
    }
)


def _load_fixture_index() -> dict[str, Any]:
    return json.loads(FIXTURE_INDEX_PATH.read_text(encoding="utf-8"))


def _load_fixture(flow: dict[str, Any]) -> dict[str, Any]:
    return json.loads((FLOWS_DIR / flow["fixture_path"]).read_text(encoding="utf-8"))


def _serialize_value(value: Any) -> str:
    """Turn a component result into searchable text (Message, Data, DataFrame, etc.)."""
    if value is None:
        return ""
    text = getattr(value, "text", None)
    if text is None and hasattr(value, "get_text"):
        try:
            text = value.get_text()
        except Exception:
            text = None
    if text is not None and str(text):
        return str(text)
    data = getattr(value, "data", None)
    if isinstance(data, dict) and data:
        return json.dumps(data, default=str)
    return str(value)


def _collect_output_text(results: list[Any]) -> str:
    chunks: list[str] = []
    for result in results:
        for out in getattr(result, "outputs", []) or []:
            for value in (getattr(out, "results", None) or {}).values():
                serialized = _serialize_value(value)
                if serialized:
                    chunks.append(serialized)
    return "\n".join(chunks)


def _collect_graph_artifacts(graph: Graph) -> str:
    """Collect built vertex results for sinks that are not chat outputs (e.g. KB ingest)."""
    from lfx.graph.utils import UnbuiltObject, UnbuiltResult

    chunks: list[str] = []
    for vertex in getattr(graph, "vertices", []) or []:
        for value in (getattr(vertex, "results", None) or {}).values():
            serialized = _serialize_value(value)
            if serialized:
                chunks.append(serialized)
        built = getattr(vertex, "built_object", None)
        if built is None or isinstance(built, UnbuiltObject):
            continue
        serialized = _serialize_value(built)
        if serialized:
            chunks.append(serialized)
        built_result = getattr(vertex, "built_result", None)
        if built_result is None or isinstance(built_result, UnbuiltResult):
            continue
        serialized = _serialize_value(built_result)
        if serialized:
            chunks.append(serialized)
    return "\n".join(chunks)


def _resolve_input_value(flow: dict[str, Any]) -> str | None:
    fields = flow.get("input_fields") or {}
    raw = fields.get("input_value")
    if raw is None:
        return None
    if isinstance(raw, str) and raw.startswith("{{") and raw.endswith("}}"):
        # Dataset placeholders resolved by integration harness; use a stable probe.
        if "chat.turn_text" in raw:
            return DEFAULT_CHAT_INPUT
        if "storage.payload_text" in raw:
            return bounded_payload_text()
        return raw
    return str(raw)


async def run_fixture_once(
    flow: dict[str, Any],
    *,
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    """Execute one fixture graph and return outputs + collected text."""
    payload = _load_fixture(flow)
    graph_data = payload.get("data", payload)
    flow_id = str(uuid.uuid4())
    graph = Graph.from_payload(graph_data, flow_id=flow_id, user_id=user_id)
    graph.prepare()
    input_value = _resolve_input_value(flow)
    inputs = [InputValueRequest(input_value=input_value, type="chat")] if input_value is not None else []
    sid = session_id or f"perf-one-run-{flow['id']}-{uuid.uuid4().hex[:8]}"
    results, session_id_out = await run_graph_internal(
        graph,
        flow_id,
        session_id=sid,
        inputs=inputs,
    )
    text = _collect_output_text(results)
    artifacts = _collect_graph_artifacts(graph)
    if artifacts:
        text = "\n".join(part for part in (text, artifacts) if part)
    return {
        "results": results,
        "session_id": session_id_out or sid,
        "text": text,
        "flow_id": flow_id,
    }


async def assert_expected_output(flow: dict[str, Any], run: dict[str, Any]) -> list[str]:
    """Return a list of violation strings (empty means pass)."""
    errors: list[str] = []
    rule = flow.get("expected_output_rule") or {}
    text = run.get("text") or ""

    if contains := rule.get("contains"):
        if contains not in text:
            errors.append(f"{flow['id']}: expected output to contain {contains!r}, got {text!r}")

    if pattern := rule.get("matches_regex"):
        if not re.search(pattern, text, flags=re.MULTILINE):
            errors.append(f"{flow['id']}: output {text!r} does not match {pattern!r}")

    if rule.get("save_to_file"):
        needle = rule.get("filename_contains") or "perf_payload"
        if needle not in text and "saved" not in text.lower() and "file" not in text.lower():
            errors.append(f"{flow['id']}: expected SaveToFile confirmation mentioning {needle!r}, got {text!r}")

    if rule.get("chat_ordering"):
        session_id = run["session_id"]
        messages = await aget_messages(session_id=session_id)
        if len(messages) < 1:
            errors.append(f"{flow['id']}: message store empty for session_id={session_id!r} (chat_db not triggered)")

    return errors


async def validate_one_runs(flow_ids: list[str] | None = None) -> list[str]:
    """Run in-process one-runs for isolators that do not need external bindings."""
    errors: list[str] = []
    manifest = _load_fixture_index()
    for flow in manifest["flows"]:
        if flow["id"] not in IN_PROCESS_ONE_RUN_IDS:
            continue
        if flow_ids and flow["id"] not in flow_ids:
            continue
        try:
            run = await run_fixture_once(flow)
            errors.extend(await assert_expected_output(flow, run))
        except Exception as exc:
            errors.append(f"{flow['id']}: one-run failed: {exc}")
    return errors
