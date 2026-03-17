"""Execution creation, status, and output extraction for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from fastapi import status
from ibm_watsonx_orchestrate_clients.tools.tool_client import ClientAPIException
from lfx.services.adapters.deployment.exceptions import DeploymentError, DeploymentNotFoundError, InvalidContentError

from langflow.services.adapters.deployment.watsonx_orchestrate.utils import extract_error_detail

if TYPE_CHECKING:
    from langflow.services.adapters.deployment.watsonx_orchestrate.types import WxOClient


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

    extra_fields = [
        "thread_id",
        "llm_params",
        "guardrails",
        "context",
        "additional_parameters",
        "environment_id",
        "version",
        "context_variables",
    ]

    payload.update({k: v for k in extra_fields if (v := provider_data.get(k)) is not None})

    return payload


async def create_agent_run(
    client: WxOClient,
    *,
    provider_data: dict[str, Any],
    deployment_id: str,
) -> dict[str, Any]:
    """Create an orchestrate run through the WxOClient wrapper."""
    query_suffix = build_orchestrate_runs_query(provider_data)
    try:
        run_payload = build_orchestrate_run_payload(
            provider_data=provider_data,
            deployment_id=deployment_id,
        )
    except ValueError as exc:
        raise InvalidContentError(message=str(exc)) from exc
    try:
        response = await asyncio.to_thread(
            client.post_run,
            query_suffix=query_suffix,
            data=run_payload,
        )
    except ClientAPIException as exc:
        if exc.response.status_code == status.HTTP_404_NOT_FOUND:
            msg = f"Agent Deployment '{deployment_id}' was not found in Watsonx Orchestrate."
            raise DeploymentNotFoundError(message=msg) from exc
        if exc.response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT:
            msg = (
                "Deployment execution request is unprocessable by Watsonx Orchestrate. "
                f"{extract_error_detail(exc.response.text)}"
            )
            raise InvalidContentError(message=msg) from exc
        raise
    return create_agent_run_result(response or {})


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


def create_agent_run_result(payload: dict[str, Any] | None) -> dict[str, Any]:
    if not payload:
        msg = "Watsonx Orchestrate returned an empty response for the execution request."
        raise DeploymentError(message=msg, error_code="empty_provider_response")

    result: dict[str, Any] = {"status": payload.get("status") or "accepted"}
    run_id = str(payload.get("run_id") or payload.get("id") or "").strip()
    if not run_id:
        msg = "Watsonx Orchestrate accepted the execution but did not return a run_id."
        raise DeploymentError(message=msg, error_code="missing_run_id")
    result["run_id"] = run_id
    return result


async def get_agent_run(client: WxOClient, *, run_id: str) -> dict[str, Any]:
    payload = await asyncio.to_thread(client.get_run, run_id)

    if not payload:
        msg = f"Watsonx Orchestrate returned an empty response when fetching execution '{run_id}'."
        raise DeploymentError(message=msg, error_code="empty_provider_response")

    status_value = str(payload.get("status") or "unknown")
    result: dict[str, Any] = {"status": status_value}

    passthrough_fields = [
        "agent_id",
        "run_id",
        "started_at",
        "completed_at",
        "failed_at",
        "cancelled_at",
        "last_error",
        "result",
    ]
    result.update({k: v for k in passthrough_fields if (v := payload.get(k)) is not None})

    return result
