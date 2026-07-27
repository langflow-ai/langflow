"""Workflows v2 protocol client for the performance suite."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from typing import Any

from tests.locust.langflow_runtime.clients.base import (
    ApiClient,
    ApplicationError,
    TransportError,
    iter_response_lines,
    parse_json_body,
    wrap_response,
)
from tests.locust.langflow_runtime.clients.sse import SseDeadlines, SseEvent, SseTruncationError, parse_sse_events

TERMINAL_STATUSES = frozenset({"completed", "failed", "timed_out", "cancelled"})
SUCCESS_STATUSES = frozenset({"completed"})


def normalize_langflow_stream_event(event: SseEvent) -> SseEvent:
    """Unwrap the Langflow adapter's logical event from an SSE data frame."""
    if event.event != "message" or not event.data:
        return event
    try:
        payload = json.loads(event.data)
    except json.JSONDecodeError:
        return event
    if not isinstance(payload, dict) or not payload.get("event"):
        return event
    data = payload.get("data")
    data_text = data if isinstance(data, str) else json.dumps(data, default=str)
    return SseEvent(event=str(payload["event"]), data=data_text, id=event.id)


@dataclass(frozen=True)
class WorkflowStatus:
    status: str
    terminal: bool
    success: bool
    raw: dict[str, Any] | None
    http_status: int


def classify_workflow_status_response(status_code: int, body: Any) -> WorkflowStatus:
    """Map GET /api/v2/workflows status responses, including terminal 408/500 bodies."""
    if isinstance(body, str):
        try:
            parsed = parse_json_body(body)
        except ApplicationError:
            parsed = {"detail": body}
    elif isinstance(body, dict):
        parsed = body
    else:
        parsed = {}

    detail = parsed.get("detail") if isinstance(parsed, dict) else None
    if isinstance(detail, dict):
        code = str(detail.get("code", ""))
        if status_code == 408 or code == "EXECUTION_TIMEOUT":
            return WorkflowStatus(
                status="timed_out",
                terminal=True,
                success=False,
                raw=parsed if isinstance(parsed, dict) else None,
                http_status=status_code,
            )
        if status_code == 500 and code == "JOB_FAILED":
            return WorkflowStatus(
                status="failed",
                terminal=True,
                success=False,
                raw=parsed if isinstance(parsed, dict) else None,
                http_status=status_code,
            )

    if status_code >= 500:
        raise TransportError(f"workflow status transport failure HTTP {status_code}")

    if status_code >= 400:
        raise ApplicationError(f"workflow status HTTP {status_code}", status_code=status_code, body=parsed)

    status_value = str(parsed.get("status", "")).lower()
    terminal = status_value in TERMINAL_STATUSES
    success = status_value in SUCCESS_STATUSES
    return WorkflowStatus(
        status=status_value or "unknown",
        terminal=terminal,
        success=success,
        raw=parsed,
        http_status=status_code,
    )


class WorkflowsClient:
    """Client for /api/v2/workflows sync, stream, background, and HITL flows."""

    def __init__(
        self,
        *,
        api: ApiClient,
        workload: str = "workflows",
        flow_class: str = "passthrough",
    ) -> None:
        self.api = api
        self.workload = workload
        self.flow_class = flow_class

    def _tx(self, operation: str) -> str:
        return ApiClient.tx_name("workflows", operation, self.workload, self.flow_class)

    def _post_body(
        self,
        *,
        flow_id: str,
        input_value: str,
        mode: str,
        session_id: str,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "flow_id": str(flow_id),
            "input_value": input_value,
            "mode": mode,
            "stream_protocol": "langflow",
            "session_id": session_id,
        }
        if idempotency_key is not None:
            body["idempotency_key"] = idempotency_key
        return body

    def run_sync(
        self,
        *,
        flow_id: str,
        input_value: str,
        session_id: str,
    ) -> dict[str, Any]:
        response = self.api.request(
            "POST",
            "/api/v2/workflows",
            name=self._tx("workflow_post_sync"),
            json=self._post_body(flow_id=flow_id, input_value=input_value, mode="sync", session_id=session_id),
        )
        parsed = wrap_response(response, expect_json=True)
        if parsed.status_code != 200:
            raise ApplicationError(
                f"sync workflow HTTP {parsed.status_code}", status_code=parsed.status_code, body=parsed.json_data
            )
        return parsed.json_data or {}

    def run_stream(
        self,
        *,
        flow_id: str,
        input_value: str,
        session_id: str,
        timeout_s: float = 60.0,
    ) -> str:
        response = self.api.request(
            "POST",
            "/api/v2/workflows",
            name=self._tx("workflow_post_stream"),
            json=self._post_body(flow_id=flow_id, input_value=input_value, mode="stream", session_id=session_id),
            stream=True,
            timeout=timeout_s,
        )
        status = int(getattr(response, "status_code", getattr(response, "status", 0)))
        if status != 200:
            parsed = wrap_response(response)
            raise ApplicationError(f"stream workflow HTTP {status}", status_code=status, body=parsed.text)

        chunks: list[str] = []
        terminal_seen = False
        for event in parse_sse_events(
            iter_response_lines(response),
            deadlines=SseDeadlines(read_s=timeout_s, idle_s=timeout_s),
        ):
            normalized_event = normalize_langflow_stream_event(event)
            chunks.append(f"event: {normalized_event.event}\ndata: {normalized_event.data}\n")
            if normalized_event.event in {"end", "error"}:
                terminal_seen = True
                break
        if not terminal_seen:
            raise SseTruncationError("workflow stream ended before terminal event")
        return "".join(chunks)

    def submit_background(
        self,
        *,
        flow_id: str,
        input_value: str,
        session_id: str,
        use_idempotency: bool = True,
        idempotency_key: str | None = None,
    ) -> str:
        key = idempotency_key or (str(uuid.uuid4()) if use_idempotency else None)
        response = self.api.request(
            "POST",
            "/api/v2/workflows",
            name=self._tx("workflow_post_background"),
            json=self._post_body(
                flow_id=flow_id,
                input_value=input_value,
                mode="background",
                session_id=session_id,
                idempotency_key=key,
            ),
        )
        parsed = wrap_response(response, expect_json=True)
        if parsed.status_code != 200:
            raise ApplicationError(
                f"background workflow HTTP {parsed.status_code}",
                status_code=parsed.status_code,
                body=parsed.json_data,
            )
        job_id = (parsed.json_data or {}).get("job_id")
        if not job_id:
            raise ApplicationError("background workflow response missing job_id", body=parsed.json_data)
        return str(job_id)

    def get_status(self, job_id: str, *, name: str | None = None, completed: bool = False) -> WorkflowStatus:
        tx = name
        if tx is None:
            tx = self._tx("get_status_completed" if completed else "get_status_poll")
        response = self.api.request(
            "GET",
            f"/api/v2/workflows?job_id={job_id}",
            name=tx,
        )
        parsed = wrap_response(response, expect_json=True)
        return classify_workflow_status_response(parsed.status_code, parsed.json_data or parsed.text)

    def wait_until_terminal(
        self,
        job_id: str,
        *,
        poll_interval_s: float = 0.25,
        deadline_s: float = 60.0,
    ) -> WorkflowStatus:
        started = time.monotonic()
        while True:
            status = self.get_status(job_id)
            if status.terminal:
                return status
            if time.monotonic() - started >= deadline_s:
                msg = f"job {job_id} did not reach terminal status within {deadline_s}s (last={status.status})"
                raise ApplicationError(msg, body=status.raw)
            time.sleep(poll_interval_s)

    def list_pending(self, flow_id: str) -> list[dict[str, Any]]:
        response = self.api.request(
            "GET",
            f"/api/v2/workflows/pending?flow_id={flow_id}",
            name=self._tx("get_pending"),
        )
        parsed = wrap_response(response, expect_json=True)
        if parsed.status_code != 200:
            raise ApplicationError(
                f"pending HTTP {parsed.status_code}", status_code=parsed.status_code, body=parsed.json_data
            )
        items = parsed.json_data
        if not isinstance(items, list):
            raise ApplicationError("pending response is not a list", body=items)
        return items

    def pending_for_job(self, flow_id: str, job_id: str) -> dict[str, Any] | None:
        for item in self.list_pending(flow_id):
            if str(item.get("job_id")) == str(job_id):
                return item
        return None

    def resume(self, job_id: str, *, request_id: str, decision: dict[str, Any] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"request_id": request_id}
        if decision is not None:
            body["decision"] = decision
        response = self.api.request(
            "POST",
            f"/api/v2/workflows/{job_id}/resume",
            name=self._tx("post_resume"),
            json=body,
        )
        parsed = wrap_response(response, expect_json=True)
        if parsed.status_code != 200:
            raise ApplicationError(
                f"resume HTTP {parsed.status_code}", status_code=parsed.status_code, body=parsed.json_data
            )
        return parsed.json_data or {}

    def _wait_for_status(
        self,
        job_id: str,
        *,
        want: set[str],
        poll_interval_s: float,
        deadline_s: float,
    ) -> WorkflowStatus:
        started = time.monotonic()
        while True:
            status = self.get_status(job_id)
            if status.status in want:
                return status
            if time.monotonic() - started >= deadline_s:
                msg = f"job {job_id} did not reach {sorted(want)} within {deadline_s}s (last={status.status})"
                raise ApplicationError(msg, body=status.raw)
            time.sleep(poll_interval_s)

    @property
    def hitl_e2e_tx(self) -> str:
        return self._tx("workflow_hitl_e2e")

    def hitl_lifecycle(
        self,
        *,
        flow_id: str,
        input_value: str,
        session_id: str,
        decision: dict[str, Any] | None = None,
        poll_interval_s: float = 0.25,
        deadline_s: float = 120.0,
    ) -> WorkflowStatus:
        job_id = self.submit_background(flow_id=flow_id, input_value=input_value, session_id=session_id)
        self._wait_for_status(job_id, want={"suspended"}, poll_interval_s=poll_interval_s, deadline_s=deadline_s)

        pending = self.pending_for_job(flow_id, job_id)
        if pending is None:
            raise ApplicationError(f"no pending row for job {job_id}")
        request_id = pending.get("request_id")
        if not request_id:
            raise ApplicationError("pending row missing request_id", body=pending)

        self.resume(job_id, request_id=str(request_id), decision=decision)
        final = self.wait_until_terminal(job_id, poll_interval_s=poll_interval_s, deadline_s=deadline_s)
        if not final.success:
            raise ApplicationError(f"HITL lifecycle did not complete successfully: {final.status}", body=final.raw)
        return final
