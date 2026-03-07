"""Execution creation, status, and output extraction for the Watsonx Orchestrate adapter."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastapi import status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException

if TYPE_CHECKING:
    from ibm_watsonx_orchestrate_clients.agents.agent_client import AgentClient


def build_orchestrate_runs_query(provider_input: dict[str, Any] | None) -> str:
    if not provider_input:
        return ""

    query_segments: list[str] = []
    for key in ("stream", "multiple_content", "stream_timeout"):
        if key not in provider_input or provider_input[key] is None:
            continue
        value = provider_input[key]
        normalized_value = str(value).lower() if isinstance(value, bool) else str(value)
        query_segments.append(f"{key}={normalized_value}")

    if not query_segments:
        return ""
    return f"?{'&'.join(query_segments)}"


def build_orchestrate_run_payload(
    *,
    provider_data: dict[str, Any],
    deployment_id: str,
) -> dict[str, Any]:
    message_payload = provider_data.get("message")
    if message_payload is None:
        message_payload = resolve_execution_message(provider_data.get("input"))

    payload: dict[str, Any] = {
        "message": message_payload,
        "agent_id": str(provider_data.get("agent_id") or deployment_id),
    }

    for key in (
        "thread_id",
        "llm_params",
        "guardrails",
        "context",
        "additional_parameters",
        "environment_id",
        "version",
        "context_variables",
    ):
        if key in provider_data and provider_data[key] is not None:
            payload[key] = provider_data[key]

    return payload


def resolve_execution_message(execution_input: str | dict[str, Any] | None) -> dict[str, Any]:
    if isinstance(execution_input, str):
        if not execution_input.strip():
            msg = "Agent execution input message must not be empty."
            raise ValueError(msg)
        return {"role": "user", "content": execution_input}

    if isinstance(execution_input, dict):
        if "role" in execution_input and "content" in execution_input:
            return execution_input

        if "message" in execution_input and isinstance(execution_input["message"], dict):
            return execution_input["message"]

        content = execution_input.get("content")
        if isinstance(content, str) and content.strip():
            return {"role": "user", "content": content}

    msg = (
        "Agent execution requires input content. Provide a non-empty string input "
        "or a message payload with 'role' and 'content'."
    )
    raise ValueError(msg)


def fetch_execution_status_payload(
    agent_client: AgentClient,
    *,
    run_id: str,
) -> dict[str, Any] | None:
    try:
        payload = agent_client._get(f"/runs/{run_id}")  # noqa: SLF001
    except ClientAPIException as exc:
        if exc.response.status_code == status.HTTP_404_NOT_FOUND:
            return None
        raise
    return payload if isinstance(payload, dict) else None


def normalize_execution_status(
    status_payload: dict[str, Any] | None,
) -> str:
    candidates: list[str] = []
    if status_payload:
        for key in (
            "status",
            "state",
            "run_status",
            "deployment_status",
            "phase",
        ):
            value = status_payload.get(key)
            if value is not None:
                candidates.append(str(value).strip().lower())

    normalized = next((value for value in candidates if value), "")
    if not normalized:
        return "in_progress"

    completed_statuses = {"completed", "complete", "success", "succeeded", "finished", "done"}
    failed_statuses = {"failed", "error", "errored", "cancelled", "canceled", "timeout"}
    in_progress_statuses = {"queued", "pending", "running", "in_progress", "processing", "accepted", "created"}

    if normalized in completed_statuses:
        return "completed"
    if normalized in failed_statuses:
        return "failed"
    if normalized in in_progress_statuses:
        return "in_progress"

    return normalized


def extract_execution_output(payload: dict[str, Any] | None) -> str | dict[str, Any] | None:
    if not payload:
        return None
    for key in ("output", "result", "response", "answer"):
        value = payload.get(key)
        if isinstance(value, str):
            if value.strip():
                return value
            continue
        if isinstance(value, dict):
            extracted = extract_text_from_payload(value)
            if isinstance(extracted, str) and extracted.strip():
                return extracted
            return value
    return extract_text_from_payload(payload)


def fetch_execution_message_output(
    agent_client: AgentClient,
    *,
    provider_input: dict[str, Any],
) -> str | dict[str, Any] | None:
    thread_id = provider_input.get("thread_id")
    message_id = provider_input.get("message_id")

    message_paths: list[str] = []
    if isinstance(thread_id, str) and thread_id.strip() and isinstance(message_id, str) and message_id.strip():
        message_paths.append(f"/threads/{thread_id}/messages/{message_id}")
    if isinstance(thread_id, str) and thread_id.strip():
        message_paths.append(f"/threads/{thread_id}/messages")
    if isinstance(message_id, str) and message_id.strip():
        message_paths.append(f"/messages/{message_id}")

    for path in message_paths:
        try:
            payload = agent_client._get(path)  # noqa: SLF001
        except ClientAPIException as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                continue
            raise

        if isinstance(payload, dict):
            output = extract_text_from_payload(payload)
            if output:
                return output
        if isinstance(payload, list):
            for item in reversed(payload):
                if isinstance(item, dict):
                    output = extract_text_from_payload(item)
                    if output:
                        return output

    return None


def extract_text_from_payload(payload: Any) -> str | dict[str, Any] | None:
    if payload is None:
        return None
    if isinstance(payload, str):
        stripped = payload.strip()
        return stripped or None
    if isinstance(payload, dict):
        for key in ("text", "content", "message", "answer", "output"):
            value = payload.get(key)
            extracted = extract_text_from_payload(value)
            if extracted:
                return extracted
        return None
    if isinstance(payload, list):
        extracted_chunks: list[str] = []
        for item in payload:
            extracted = extract_text_from_payload(item)
            if isinstance(extracted, str) and extracted:
                extracted_chunks.append(extracted)
        if extracted_chunks:
            return "\n".join(extracted_chunks)
        return None
    return None
