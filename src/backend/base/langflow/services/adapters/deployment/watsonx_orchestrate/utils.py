"""Name validation, error helpers, and misc utilities for the Watsonx Orchestrate adapter."""

from __future__ import annotations

import json
from typing import Any

from lfx.services.adapters.deployment.exceptions import InvalidContentError

from langflow.services.adapters.deployment.watsonx_orchestrate.constants import (
    _WXO_SANITIZE_RE,
    _WXO_TRANSLATE,
)


def normalize_wxo_name(s: str) -> str:
    return _WXO_SANITIZE_RE.sub("", s.translate(_WXO_TRANSLATE))


def validate_wxo_name(name: str) -> str:
    """Normalize and validate a WXO resource name."""
    normalized_name = normalize_wxo_name(str(name))
    if not normalized_name:
        msg = "Deployment name must include at least one alphanumeric character."
        raise InvalidContentError(message=msg)
    if not normalized_name[0].isalpha():
        msg = "Deployment name must start with a letter. "
        raise InvalidContentError(message=msg)
    return normalized_name


def require_non_empty_string(
    s: Any,
    *,
    field_name: str,
    error_message: str | None = None,
) -> str:
    if isinstance(s, str) and (_value := s.strip()):
        return _value
    msg = error_message or f"Expected non-empty string for '{field_name}'."
    raise ValueError(msg)


def require_tool_id(tool_response: dict[str, Any]) -> str:
    tool_id = tool_response.get("id")
    if not tool_id:
        msg = "WXO did not return a tool id for snapshot creation."
        raise ValueError(msg)
    return tool_id


def dedupe_list(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def require_exclusive_resource(
    *,
    resource: str,
    _id: str | list[str] | None,
    payload: dict[str, Any] | None,
    msg_prefix: str = "",
) -> None:
    """Require exactly one of the resource id or payload to be present and non-empty and non-null."""
    if (not _id) == (not payload):
        msg = f"{msg_prefix}Exactly one of {resource} id or payload should be present and non-empty and non-null."
        raise ValueError(msg)


def extract_error_detail(response_text: str) -> str | dict:
    """Extract a human-readable error detail from a ClientAPIException response.

    The response body may contain a ``detail`` value that is a string, a dict
    with a ``msg`` key, or a list of such dicts.  This helper normalises all
    three shapes into a single value suitable for inclusion in an error message.
    """
    try:
        detail = json.loads(response_text).get("detail")
    except (TypeError, ValueError, json.JSONDecodeError):
        return response_text
    if detail and isinstance(detail, list):
        detail = detail[0]
    if isinstance(detail, dict):
        detail = detail.get("msg") or detail
    return detail


def build_agent_payload(
    *,
    data: Any,
    tool_ids: list[str],
) -> dict[str, Any]:
    if data.provider_spec is None:
        msg = "Deployment data must include provider_spec with a non-empty name and display_name."
        raise InvalidContentError(message=msg)
    return {
        "name": data.provider_spec["name"],
        "display_name": data.provider_spec["display_name"],
        "description": str(data.description or "").strip() or f"Langflow deployment {data.name}",
        "tools": tool_ids,
        "style": "default",
        # TODO: do not hard code this?
        # but then we need to make a api request
        # to retrieve the available llms in wxo,
        # which isn't great either.
        # sadly, the llm field is required by the wxo api.
        "llm": "groq/openai/gpt-oss-120b",
    }


def extract_agent_tool_ids(agent: dict[str, Any]) -> list[str]:
    # Shape source:
    # - SDK/API agent payload uses "tools" as list[str] in this adapter flow.
    return [str(tool_id) for tool_id in agent.get("tools", []) if tool_id]


def extract_agent_connection_ids(agent: dict[str, Any]) -> list[str]:
    # Shape source:
    # - SDK/API agent payload uses "connection_ids" as list[str].
    return [str(connection_id) for connection_id in agent.get("connection_ids", []) if connection_id]
